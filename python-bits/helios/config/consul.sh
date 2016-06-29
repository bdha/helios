#!/usr/bin/ksh

until [ -f /opt/helium/etc/helios.json ] ; do
  echo "waiting for config file"
  sleep 5
done

CONSUL_PASS=`json -f /opt/helium/etc/helios.json consul_pass`
CONSUL_HOST=`json -f /opt/helium/etc/helios.json consul_host`
CONSUL_DC=`json -f /opt/helium/etc/helios.json consul_dc`
HOSTIP=`ifconfig net0 | grep inet | awk '{print $2}'`

/opt/local/bin/consul agent -join=$CONSUL_HOST -data-dir=/var/consul \
  -bind $HOSTIP \
  -encrypt="$CONSUL_PASS" \
  -dc=$CONSUL_DC &
