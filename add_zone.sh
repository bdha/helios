#!/usr/bin/ksh

#set -v

## First we'd spin a new zone, with the 'base' image using vmadm or whatever, then we'd get the zonename and wait for it to come up

## TODO, bryan can implement this bit

ZONENAME=$2

## TODO, consul doesn't listen on 0.0.0.0, so we need to know the 'network' ip, ugh
IP="10.50.40.71:8500"

NODEINFO=`curl -s http://$IP/v1/catalog/node/$ZONENAME`
echo "waiting for zone $ZONENAME to come up"

while [ "$NODEINFO" = "null" ]; do
	sleep 5
	NODEINFO=`curl -s http://$IP/v1/catalog/node/$ZONENAME`
done

ADDRESS=`echo "$NODEINFO" | json Node.Address`

#RES=`curl -s -X PUT -H "Content-Type: application/json" -d "{\"Node\": \"$ZONENAME\", \"Address\": \"$ADDRESS\", \"Service\": {\"Service\": \"$1\"}}" http://$IP/v1/catalog/register`
RES=`curl -s -X PUT -d "$1" http://$IP/v1/kv/$ZONENAME/services`

if [ "$RES" != "true" ]; then
	echo "Failed to register service $1 on $ZONENAME: $RES"
	exit 1
fi

## wait for the service to register itself, so we know stuff worked
RES=`curl -s http://$IP/v1/catalog/node/$ZONENAME | json Services.$1`
echo "--$RES--"

while [ "$RES" = "{}" -o "$RES" = "" ]; do
	sleep 5
	RES=`curl -s http://$IP/v1/catalog/node/$ZONENAME | json Services.$1`
	echo "--$RES--"
done

echo "Service $1 registered on $ZONENAME"
