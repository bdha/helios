from helios import app
from flask import Flask, jsonify, request, Response

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
    zones = subprocess.check_output(["/opt/local/bin/triton", "--profile", "helium-staging", "ls", "-j"])
    return zones

def get_service_version(name):
    c = consul.Consul()
    index, data = c.kv.get("service/{0}/version".format(name))
    return "{0}".format(data['Value'].decode('utf-8'))

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
      nodes['members'][upgrade]['upgrading'] = True

    return nodes

def get_service_health(name):
    c = consul.Consul()
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

    failing_nodes = set()

    for x in c.health.service(name)[1]:
      health['nodes_total'] = health['nodes_total'] + 1
      for y in x['Checks']:
        health['checks_total'] = health['checks_total'] +1

        health[ 'checks_' + y['Status'] ] = health[ 'checks_' + y['Status'] ] +1

        if y['Status'] != "passing":
          health['service_state'] = "sad"
          health['checks_failing'] = health['checks_failing'] +1
          failing_nodes.add(x['Node']['Node'])

    health['checks_failing_per'] = ( health['checks_failing'] / health['checks_total'] ) * 100

    health['nodes_faulted'] = len(failing_nodes)
    health['nodes_faulted_per'] = ( health['nodes_faulted'] / health['nodes_total'] ) * 100

    return health

@app.route('/services/<name>', methods = ['GET'])
def service(name):
    health  = get_service_health(name)
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

# POST Create a new instance of a service
# This creates a zone.
# Returns the nodename.
# Need a service/package map.
# -d { "service": "router", "size": "package name" }
#@app.route('/instances', methods = ['POST'])

# GET all instances of services
#@app.route('/instances' methods = ['GET'])

# PUT Change or set an instance's role.
# Must be a single string.
#@app.route('/instances/<instance>/role

# PUT Change an instance's state.
# e.g., start, reboot, stop, mark down, mark up
# start, reboot, stop are Triton commands.
# mark down/up are Helios states the agent will notice and act on.
#@app.route('/instances/<instance>/state/<state>

# DELETE an instance.
# This destroys the zone.
#@app.route('/instances/<instance>', methods = ['DELETE'])

# GET Show one instance.
# Returns a list of the services it provides, its provisioning status, IP addr, health, etc.
#@app.route('/instances/<instance>', methods = ['GET'])

# PUT Set arbitrary instance config.
# -d { "value": "thing" }
#@app.route('/instances/:instance/config/<key>', methods = ['PUT']))

# DELETE Delete a config key.
#@app.route('/instances/:instance/config/<key>', methods = ['DELETE']))
