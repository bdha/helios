#!/usr/bin/env python
import consul
import subprocess
import netifaces
import time
import os
import socket
import json
import hashlib
import glob
import pystache


def read_required_key(c, key):
    index = None
    data = None
    while data == None:
        index, data = c.kv.get(key, index=index)
        if data:
            return data['Value'].decode("utf-8")

def get_current_session(c, zonename, service):
    index = None
    current_session = None
    index, data = c.kv.get('sessions/{0}/{1}'.format(zonename, service))
    if data != None:
            try:
                current_session = data['Value'].decode("utf-8")
                print("current session is {0}".format(current_session))
                index, data2  = c.session.info(current_session)
                if data2:
                    return current_session
                else:
                    return None
            except consul.base.ConsulException:
                return None
    return None

def check_service_symlink(service, current_version):
    try:
        path = os.readlink("/opt/helium/{0}/current".format(service))
        if path[-1] == '/':
            path = path[:-1]
        head, tail = os.path.split(path)
        if tail.startswith("{0}-".format(service)):
            return tail[len(service)+1:]
        return None
    except OSError:
        return None

def get_upgrade_session(c, service, zonename):
    ## clean up any stale upgrade sessions for this node
    index, sessions = c.session.list()
    for session in sessions:
        if session['Node'] == zonename and session['Name'] == "{0}-upgrade".format(service):
                c.session.destroy(session["ID"])
    session = c.session.create(name="{0}-upgrade".format(service), lock_delay=0, ttl=3600, behavior='delete')
    return session

def get_upgrade_lock(c, service, zonename):
    ## obtain the upgrade lock
    ## first create a session tied only to node health that has a TTL of one hour
    ## if this node crashes, the lock should be released
    session = get_upgrade_session(c, service, zonename)
    locked = False
    while locked == False:
        locked = c.kv.put("service/{0}/upgrade".format(service), zonename, acquire=session)
    return session

def release_upgrade_lock(c, session):
    c.session.destroy(session)

def go_out_of_service(c, cnsname):
    subprocess.call(["mdata-put", "triton.cns.status", "down"])
    c.agent.maintenance(True, "upgrade")

    ## check CNS knows we're down
    foo=netifaces.ifaddresses('net0')
    host_ip=foo[netifaces.AF_INET][0]['addr']
    hostname, aliases, addresses = socket.gethostbyname_ex(cnsname)
    ## XXX this seems to end up using the system resolver, which is 8.8.8.8, which is caching a lot
    return
    print("waiting for CNS to report us down")
    while host_ip in addresses:
        time.sleep(5)
        hostname, aliases, addresses = socket.gethostbyname_ex(cnsname)

def enter_service(c):
    subprocess.call(["mdata-put", "triton.cns.status", "up"])
    c.agent.maintenance(False, "upgrade")

def maybe_disable_service(c, service):
    status = subprocess.Popen("svcs -H {0}".format(service), shell=True, stdout=subprocess.PIPE).stdout.read().rstrip()
    if status == '':
        ## service not installed
        return
    subprocess.call(["svcadm", "disable", service])
    ## wait for at least one of the service's checks to go critical
    while True:
        checks = c.agent.checks()
        service_has_checks = False
        for key, value in checks.items():
            if value['ServiceName'] == service:
                service_has_checks = True
        if service_has_checks == False:
                return
        for key, value in checks.items():
            if value['ServiceName'] == service and value['Status'] == "critical":
                return
        time.sleep(5)

def fetch_artefact(service, version):
    ## TODO some goddamn s3 thing, I don't know
    return "{0}-{1}-sunos.tgz".format(service, version)

def install_artefact(service, version, filename):
    subprocess.call(["mkdir", "-p", "/opt/helium/{0}".format(service)])
    subprocess.call(["tar", "-C", "/opt/helium/{0}".format(service), "-xf", filename])
    subprocess.call(["rm", "-f", "/opt/helium/{0}/current".format(service)])
    subprocess.call(["ln", "-sf", "/opt/helium/{0}/{0}-{1}/".format(service, version), "/opt/helium/{0}/current".format(service)])
    
def register_check(c, service, check_filename):
    with open(check_filename) as check_file:
        check = json.load(check_file)
        checkobj = None
        if 'tcp' in check:
            hostport = check['tcp'].split(':')
            checkobj = consul.Check.tcp(hostport[0], int(hostport[1]), check['interval'], timeout=check['timeout'])
        elif 'http' in check:
            checkobj = consul.Check.http(check['http'], check['interval'], timeout=check['timeout'])
        elif 'script' in check:
            checkobj = consul.Check.script(check['script'], check['interval'])

        if checkobj != None:
                c.agent.check.register(check['name'], checkobj, service_id=check['serviceid'])

def get_package_info(service):
    with open('/opt/helium/{0}/current/helios/package.json'.format(service)) as pkg_file:
        pkg_info = json.load(pkg_file)
    return pkg_info

def install_package(packagename):
    res = subprocess.call(["pkgin", "-y", "install", packagename])
    ## TODO fail more dramatically here?
    if res != 0:
        print("Unable to install package {0}".format(packagename))

def ensure_packages(service):
    pkg_info = get_package_info(service)
    if 'packages' in pkg_info:
        for package in pkg_info['packages']:
                install_package(package)

def ensure_roles(c, zonename, service, cnsname):
    pkg_info = get_package_info(service)
    if 'roles' in pkg_info:
        for role in pkg_info['roles']:
           check_service(c, zonename, role, cnsname, False)

def smfgen(servicename):
    subprocess.call("smfgen < /opt/helium/{0}/current/helios/config/service.json > /opt/helium/{0}/current/helios/config/service.xml".format(servicename), shell=True)

def ensure_user(userfilename):
    with open(userfilename) as user_file:
        user = json.load(user_file)
    if 'home' in user and 'id' in user:
        ## check the user and group exist
        group_exists = subprocess.call(["getent", "group", user['id']])
        if group_exists != 0:
            cmd = ["groupadd"]
            if 'gid' in user:
                cmd.extend(["-g", str(user['gid'])])
            cmd.extend([user['id']])
            print(cmd)
            subprocess.call(cmd)
        user_exists = subprocess.call(["getent", "passwd", user['id']])
        if user_exists != 0:
            ## #useradd -g 3003 -u 3003 -c "Helium Router" -s /bin/bash -d /opt/helium/router router
            cmd = ["useradd", "-g", user['id']]
            if 'uid' in user:
                cmd.extend(["-u", str(user['uid'])])
            if 'shell' in user:
                cmd.extend(["-s", user['shell']])
            if 'home' in user:
                cmd.extend(["-d", user['home']])
            if 'groups' in user:
                cmd.extend(["-G", ",".join(user['groups'])])
            cmd.extend(["-m", user['id']])
            print(cmd)
            subprocess.call(cmd)

def ensure_users(service):
    userfiles = glob.glob("/opt/helium/{0}/current/helios/config/users/*.json".format(service))
    print(userfiles)
    for userfile in userfiles:
        ensure_user(userfile)

## this can be used for primary and auxiliary services (like pgbouncer)
def check_service(c, zonename, service, cnsname, primary=False):
    version = read_required_key(c, 'service/{0}/version'.format(service))

    services = c.agent.services()
    tags = []
    if service in services:
        tags = services[service]['Tags']

    current_config = None
    current_version = None
    for tag in tags:
            if tag.startswith("config-"):
                    current_config = tag[len("config-"):]
            elif tag.startswith("version-"):
                    current_version = tag[len("version-"):]

   
    current_fs_version = check_service_symlink(service, current_version)
    if current_fs_version == None or current_version != current_fs_version:
        current_version = None

    installed = False
    if version != current_version:
        print("upgrading service to {0}".format(version))
        upgrade_session = get_upgrade_lock(c, service, zonename)
        go_out_of_service(c, cnsname)
        maybe_disable_service(c, service)
        filename = fetch_artefact(service, version)
        install_artefact(service, version, filename)
        ensure_packages(service)
        ensure_users(service)
        # ensure_roles(c, zonename, service, cnsname),
        smfgen(service)
        ## Run the install hook
        subprocess.call(["/opt/helium/{0}/current/helios/hooks/install.sh".format(service)])
        installed = True

    ## compute the config SHA and compare it to the one in the tag
    index, configs = c.kv.get("service/{0}/config".format(service), recurse=True)
    json_config = {}
    if configs != None:
        for config in configs:
            json_config[config['Key'].split('/')[-1]] = config['Value'].decode("utf-8")
 
    foo=netifaces.ifaddresses('net0')
    host_ip=foo[netifaces.AF_INET][0]['addr']
    json_config['host_ip'] = host_ip

    json_data = json.dumps(json_config, sort_keys=True, indent=4, separators=(',', ': '))

    text_file = open("data.json", "w")
    text_file.write(json_data)
    text_file.close()
    config_version = hashlib.sha1(json_data.encode("utf-8")).hexdigest()

    configured = False
    if config_version != current_config or installed == True:
        ## find all .mustache files in /opt/helium/$SERVICE/current and template them
        with open('/opt/helium/{0}/current/helios/default.json'.format(service)) as defaults_file:
             defaults = json.load(defaults_file)
        merged_config = {**defaults, **json_config}
        mustaches = glob.glob("/opt/helium/{0}/current/**/*.mustache".format(service), recursive=True)
        renderer = pystache.Renderer()
        for m in mustaches:
                new_file = renderer.render_path(m, merged_config)
                new_file_name, ext = os.path.splitext(m)
                text_file = open(new_file_name, "w")
                text_file.write(new_file)
                text_file.close()
       
        subprocess.call(["/opt/helium/{0}/current/helios/hooks/config.sh".format(service)])
        configured = True

    current_session = None
    if primary == True:
        current_session = get_current_session(c, zonename, service)
    
    if installed == True or configured == True:
        ## import the new service definition, it might have changed
        subprocess.call(["svccfg", "import", "/opt/helium/{0}/current/helios/config/service.xml".format(service)])
        subprocess.call(["svcadm", "enable", service])
        subprocess.call(["svcadm", "clear", service])

        c.agent.service.deregister(service)
        c.agent.service.register(service, tags=["version-{0}".format(version), "config-{0}".format(config_version)])
        checks = glob.glob("/opt/helium/{0}/current/helios/checks/*.json".format(service))
        for check in checks:
                register_check(c, service, check)
        ## destroy any old leader session
        if current_session:
            c.session.destroy(current_session)
            current_session = None 

        print("waiting for health checks to go green")
        while True:
            checks = c.agent.checks()
            services = []
            for key, value in checks.items():
                if value['ServiceName'] == service:
                    services.append(value)
            if all(s['Status'] == 'passing' for s in services):
                break
            time.sleep(5)
        ## ok, the service is green now, release the upgrade lock and leave maintenance mode
        release_upgrade_lock(c, upgrade_session)
        enter_service(c)

    if current_session == None and primary == True:
        print("creating new session")
        ## create a new leader session using the service's checks
        checks = c.agent.checks()
        servicenames = ['serfHealth']
        for key, value in checks.items():
            if value['ServiceName'] == service:
                servicenames.append(value['CheckID'])
        try:
            current_session = c.session.create("{0}-leader".format(service), checks=servicenames, lock_delay=0, ttl=120, behavior='delete')
        except consul.base.ConsulException:
            ## can't create the session because the service is down
            print("service is DOWN")
            return
        res = c.kv.put('sessions/{0}/{1}'.format(zonename, service), current_session)
        print(res)
    elif primary == True:
        print("renewing session")
        ## renew the session
        c.session.renew(current_session)
    
    if primary == True:
        locked = c.kv.put("service/{0}/leader".format(service), zonename, acquire=current_session)
        if locked:
            print("we are the leader")
        else:
            print("we are not the leader")

def main():
    c = consul.Consul()
    zonename = subprocess.Popen("zonename", shell=True, stdout=subprocess.PIPE).stdout.read().rstrip().decode("utf-8")
    cnsname="helios.kwatz.helium.zone"
    foo=netifaces.ifaddresses('net0')
    host_ip=foo[netifaces.AF_INET][0]['addr']

    index = None
    service = read_required_key(c, "nodes/{0!s}/services".format(zonename))

    while True:
        check_service(c, zonename, service, cnsname, primary=True)
        time.sleep(5)


if __name__ == '__main__':
    main()
