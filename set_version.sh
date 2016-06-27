#!/usr/bin/ksh

SERVICE=$1
VERSION=$2

## TODO, consul doesn't listen on 0.0.0.0, so we need to know the 'network' ip, ugh
IP="10.50.40.71:8500"

curl -X PUT -d "$VERSION" http://$IP/v1/kv/service/$SERVICE/version
