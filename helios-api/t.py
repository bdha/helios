import re
import json
import pprint
import subprocess
from prettytable import PrettyTable

pp = pprint.PrettyPrinter(indent=4)

svc_health  = "/opt/local/bin/curl -s -X GET localhost:5000/services/router/helath"


svc_health        = subprocess.check_output(["/opt/local/bin/curl", "-s", "-X", "GET", "localhost:5000/services/router/health"])
svc_health_str    = svc_health.decode('utf-8')
svc_health_json   = json.loads(svc_health_str)

svc_version       = subprocess.check_output(["/opt/local/bin/curl", "-s", "-X", "GET", "localhost:5000/services/router/version"])
svc_version_str   = svc_version.decode('utf-8')
svc_version_json  = json.loads(svc_version_str)

x = PrettyTable(["ID", "NAME", "STATE", "HEALTH", "VERSION", "FLAGS", "AGE"])
x.align = "l"
x.border = False
x.padding_width = 2
x.left_padding_width=0
x.sortby="ID"

for k in svc_health_json['members'].keys():

  flags = []

  if 'upgrading' in svc_version_json['nodes']['members'][k]:
    flags.append("U")

  if svc_health_json['members'][k]['firewall'] is True:
    flags.append("F")

  f = ''.join(flags)

  version = ""
  # Visually mark zones that are out of spec.
  if "version" in svc_version_json['nodes']['members'][k]:
    version = svc_version_json['nodes']['members'][k]['version']
    if svc_version_json['version'] != version:
      version = re.sub(r"$", "*", version)

  zone_id = re.sub(r"-.*$", "", k)
  zone_name   = svc_health_json['members'][k]['name']
  zone_state  = svc_health_json['members'][k]['state']
  zone_age    = svc_health_json['members'][k]['created']

  svc_state   = svc_health_json['members'][k]['service_state']

  x.add_row([zone_id, zone_name, zone_state, svc_state, version, f, zone_age])

print(x)
