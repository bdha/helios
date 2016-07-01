from helios import app
from flask import Flask, jsonify, request, Response
import re
import consul
import subprocess
import json
import pprint

pp = pprint.PrettyPrinter(indent=4)

@app.route('/')
def index():
    return 'sol'

@app.route('/zones/list')
def zones_list():
    zones = subprocess.check_output(["/opt/local/bin/triton", "--profile", "helium-dev", "ls", "-j"])

    # triton ls -j returns effective garbage, which requires munging.
    zones = re.sub(r"}\n", "},", zones.decode('utf-8'))
    zones = re.sub(r",$", "", zones)

    zones_json = json.loads("[" + zones + "]")

    return zones_json

def get_service_version(name):
    c = consul.Consul()
    index, data = c.kv.get("service/{0}/version".format(name))
    return "{0}".format(data['Value'].decode('utf-8'))

# router versions: 
# f0544e6 and a1a8d3b
def set_service_version(name, version):
    # XXX Verify version exists in the artefact store.
    c = consul.Consul()
    rc = c.kv.put("service/"+name+"/version", version)
    print("Setting "+name+" to version "+version+": "+str(rc))
    return rc

def get_service_version_nodes(name):
    c = consul.Consul()

    nodes             = {}
    nodes['members']  = {}
    nodes['coverage'] = {}

    nodes_total   = 0
    version       = get_service_version(name)
    synced_nodes  = set()

    for x in c.health.service(name)[1]:
      nodes_total = nodes_total +1
      node = x['Node']['Node']
      nodes['members'][node] = {}
      for t in x['Service']['Tags']:
        key, value = t.split('-')
        nodes['members'][node][key] = value
        if key == "version" and value == version:
            synced_nodes.add(node) 

    nodes['coverage']['waiting']      = nodes_total - len(synced_nodes)
    nodes['coverage']['upgraded']     = len(synced_nodes)
    nodes['coverage']['total_per']        = ( len(synced_nodes) / nodes_total ) * 100

    index, upgrade = c.kv.get("service/{0}/upgrade".format(name))
    # "upgrade" contains the node name.
    if upgrade is not None:
      zone_id = format(upgrade['Value'].decode('utf-8'))
      nodes['members'][zone_id] = {}
      nodes['members'][zone_id]['upgrading'] = True

    return nodes

@app.route('/services/<name>/health', methods = ['GET'])
def get_service_health(name):
    c = consul.Consul()
    
    zones = zones_list()

    # Global stats.
    health = {}
    health['service_state'] = "happy"
    health['nodes_total'] = 0
    health['nodes_faulted'] = 0
    health['nodes_faulted_per'] = 0
    health['checks_total'] = 0
    health['checks_passing'] = 0
    health['checks_warning'] = 0
    health['checks_failing'] = 0
    health['checks_critical'] = 0
    health['checks_failing_per'] = 0

    health['members'] = {}

    failing_nodes = set()

    for x in c.health.service(name)[1]:
      health['nodes_total'] = health['nodes_total'] + 1

      zone_id = x['Node']['Node']

      match = next((l for l in zones if l['id'] == zone_id) , None)

      if match is None:
        break

      if match['state'] == "deleted":
        break

      # Per-node stats.
      health['members'][zone_id] = {}
      health['members'][zone_id]['service_state'] = "happy"
      health['members'][zone_id]['checks_total'] = 0
      health['members'][zone_id]['checks_passing'] = 0
      health['members'][zone_id]['checks_warning'] = 0
      health['members'][zone_id]['checks_failing'] = 0
      health['members'][zone_id]['checks_critical'] = 0

      #health['members'][zone_id]['state'] = zones[zone_id]['state']
      #(item for item in zones if item["id"] == zone_id).next()
      
      health['members'][zone_id]['name']      = match['name']
      health['members'][zone_id]['state']     = match['state']
      health['members'][zone_id]['firewall']  = match['firewall_enabled']
      health['members'][zone_id]['package']   = match['package']
      health['members'][zone_id]['created']   = match['created']

      for y in x['Checks']:
        health['checks_total'] = health['checks_total'] +1

        health[ 'checks_' + y['Status'] ] = health[ 'checks_' + y['Status'] ] +1
        health['members'][zone_id]['checks_' + y['Status']] = health['members'][zone_id]['checks_' + y['Status']] +1

        if y['Status'] != "passing":
          health['service_state'] = "sad"
          health['checks_failing'] = health['checks_failing'] +1
          failing_nodes.add(zone_id)

          health['members'][zone_id]['service_state'] = "sad"

    health['checks_failing_per'] = ( health['checks_failing'] / health['checks_total'] ) * 100

    health['nodes_faulted'] = len(failing_nodes)
    health['nodes_faulted_per'] = ( health['nodes_faulted'] / health['nodes_total'] ) * 100

    j = json.dumps(health)
    return j

@app.route('/services/<name>', methods = ['GET'])
def service(name):
    health  = json.loads(get_service_health(name))
    version = get_service_version(name)

    node = {}
    node['health']  = health
    node['version'] = version

    j = json.dumps(node)
    return j

@app.route('/services/<name>/version', methods = ['GET'])
def service_version_get(name):
    node = {}
    node['version'] = get_service_version(name)

    node['nodes'] = get_service_version_nodes(name)
    return json.dumps(node)

@app.route('/services/<name>/version/<version>', methods = ['PUT'])
def service_version_set(name, version):
    node = {}
    node['previous_version'] = get_service_version(name)

    # XXX Check RC
    set_version = set_service_version(name, version)

    node['version'] = get_service_version(name)
    return json.dumps(node)

@app.route('/services', methods = ['GET'])
def services_list():
      s = []
      c = consul.Consul()

      for k in c.catalog.services()[1].keys():
        s.append(k)

      j = json.dumps(s)
      return j

# PUT Set arbitrary service config.
# -d { "value": "thing" }
#@app.route('/services/<service>/config/<key>', methods = ['PUT']))

# DELETE Delete a config key.
#@app.route('/services/<service>/config/<key>', methods = ['DELETE']))

# POST Create a new instance of a service
# -d { "service": "router", "size": "package name" }
@app.route('/instances', methods = ['POST'])
def create_instance():
    machine_id   = "helios@0.0.3"
    machine_size = "he1-standard-2-smartos"

    if request.headers['Content-Type'] != 'application/json':
      return "415 Unsupported Media Type"

    service = request.json['service']
    print("instantiating new " + service)
    zone = subprocess.check_output(["/opt/local/bin/triton", "--profile", "helium-dev", "inst", "create", "-j", "-t", "role=esupervisor", "-t", "helios="+ service, "--script=/root/bootstrap.sh", machine_id, machine_size])

    s = str(zone.decode('utf-8'))
    j = json.loads(s)

    zone_id = j['id']

    print(zone_id + ": " + service)

    r             = {}
    r['id']       = zone_id
    r['state']    = j['state']
    r['service']  = service

    c = consul.Consul()
    rc = c.kv.put("nodes/"+zone_id+"/services", service)
    print(zone_id + ": role set: " + str(rc))

    r['role_set'] = rc

    return json.dumps(r)

# GET all instances of services
# This should be curated data. It should return:
#   * ID, NAME, IMG, PACKAGE, STATE, FLAGS, PRIMARYIP, CREATED
#@app.route('/instances' methods = ['GET'])

# GET an instances state.
# This will return the zone status, and the defined service status.
# For instance: The zone might be "running", but the service might be "down".
# Or the zone might be "provisioning" or "stopped", but the service is defined
# as "up", so when the zone comes back up, the service will start. By default,
# the service will be up.
#@app.route('/instances/<instance>/state, methods = ['GET'])

# PUT Change an instance's state.
# e.g., start, reboot, stop, mark down, mark up
# start, reboot, stop are Triton commands.
# mark down/up are Helios states the agent will notice and act on.
#@app.route('/instances/<instance>/state/<state>, methods = ['PUT'])

# DELETE an instance.
# This destroys the zone.
#@app.route('/instances/<instance>', methods = ['DELETE'])

# GET Show one instance.
# Returns a list of the services it provides, its provisioning status, IP addr, health, etc.
#@app.route('/instances/<instance>', methods = ['GET'])

# ? Cleanup stale Consul entries.
# If node entries exist without corresponding zones running, delete the node /
# KV entries.
# -d '{ "cleanup": true }' or /cleanup ?
#@app.route('/instances', methods = ['PUT'])
