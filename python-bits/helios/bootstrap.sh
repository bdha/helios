#!/usr/bin/ksh

## XXX this is probably only useful for imeage generation, helios can upgrade itself in the field

HELIOSDIR="$(dirname $(readlink -f $(dirname "$0")))"
rm -rf /opt/helium/helios/current
ln -sf $HELIOSDIR /opt/helium/helios/current
npm install -g smfgen
## apparently libpython doesn't end up in the package, bleh
pkgin -y install python35
pkgin -y install consul
## if we want to create home directories here, we need to make sure the base dir exists
mkdir /var/helium
smfgen < /opt/helium/helios/current/helios/config/service.json > /opt/helium/helios/current/helios/config/service.xml
# XXX we can't smfgen consul because smfgen insists on backgrounding all start scripts
svccfg import /opt/helium/helios/current/helios/config/consul.xml
svccfg import /opt/helium/helios/current/helios/config/service.xml
svcadm clear consul
svcadm clear helios
