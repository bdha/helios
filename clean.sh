#!/usr/bin/ksh

ZONENAME=`zonename`

SERVICE=`curl -s http://127.0.0.1:8500/v1/kv/nodes/$ZONENAME/services | json 0.Value | base64 -d`

curl -s http://127.0.0.1:8500/v1/agent/service/deregister/$SERVICE

curl -s -X DELETE http://127.0.0.1:8500/v1/kv/nodes/$ZONENAME/services
