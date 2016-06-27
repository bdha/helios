#!/usr/bin/ksh

SERVICE=$1
VARNAME=$2
VALUE=$3

## TODO, consul doesn't listen on 0.0.0.0, so we need to know the 'network' ip, ugh
IP="10.50.40.71:8500"

curl -X PUT -d "$VALUE" http://$IP/v1/kv/service/$SERVICE/config/$VARNAME
