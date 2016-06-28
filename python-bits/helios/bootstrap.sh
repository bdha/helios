#!/usr/bin/ksh

## XXX this is probably only useful for imeage generation, helios can upgrade itself in the field

HELIOSDIR="$(dirname $(readlink -f $(dirname "$0")))"
rm -rf /opt/helium/helios/current
ln -sf $HELIOSDIR /opt/helium/helios/current
npm install -g smfgen
smfgen < /opt/helium/helios/current/helios/config/service.json > /opt/helium/helios/current/helios/config/service.xml
svccfg import /opt/helium/helios/current/helios/config/service.xml
svcadm clear helios
