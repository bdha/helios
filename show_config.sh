#!/usr/bin/ksh

SERVICE=$1

## TODO, consul doesn't listen on 0.0.0.0, so we need to know the 'network' ip, ugh
IP="10.50.40.71:8500"

curl -s http://$IP/v1/kv/$SERVICE/config?recurse=1 | json -a Key Value | awk -v service=$SERVICE '{sub(/\w+\/config\//, "", $1)}{"base64 -d<<< \""$2"\""|getline $4}{printf "    \"%s\":%s,\n", $1, $4}'
