#!/usr/bin/ksh

ZONENAME=`zonename`

export SERVICE=`curl -s http://127.0.0.1:8500/v1/kv/$ZONENAME/services | json 0.Value | base64 -d`

while [ "$SERVICE" = "" ]; do
	echo $SERVICE
	sleep 5
	SERVICE=`curl -s http://127.0.0.1:8500/v1/kv/$ZONENAME/services | json 0.Value | base64 -d`
done

## download the tarball

VERSION=`curl -s http://127.0.0.1:8500/v1/kv/$SERVICE/version | json 0.Value | base64 -d`

CURRENT_VERSION=`curl -s http://127.0.0.1:8500/v1/agent/services | json $SERVICE.Tags | grep version | awk -F- '{sub(/",?/, "", $2); print $2}'`
CURRENT_CONFIG=`curl -s http://127.0.0.1:8500/v1/agent/services | json $SERVICE.Tags | grep config | awk -F- '{sub(/",?/, "", $2); print $2}'`
## we can't put a session in a tag, I don't think, because of when we create a session vs when we create a service
CURRENT_SESSION=`curl -s http://127.0.0.1:8500/v1/kv/sessions/$ZONENAME/$SERVICE | json 0.Value | base64 -d`

SESSION_INFO=`curl -s http://127.0.0.1:8500/v1/session/info/$CURRENT_SESSION`

echo "$SESSION_INFO" | json 2>&1 > /dev/null

#echo $?

if [ $? -ne 0 -o "$SESSION_INFO" = "[]" ]; then
	CURRENT_SESSION=""
	if [ -n $CURRENT_SESSION ]; then
		curl -s -X DELETE http://127.0.0.1:8500/v1/kv/sessions/$ZONENAME/$SERVICE > /dev/null
	fi
fi

## check that the filesystem agrees
if [ -h "/opt/helium/$SERVICE/current" ]; then
	CURRENT_LOCATION=`readlink /opt/helium/$SERVICE/current`
	CURRENT_FS_VERSION=`basename $CURRENT_LOCATION | awk -F- '{print $2}'`
	if [ "$CURRENT_VERSION" != "$CURRENT_FS_VERSION" ]; then
		## something is hosed up, just reconverge
		CURRENT_VERSION=""
	fi
else
	## we don't have a 'current' symlink at all, reconverge
	CURRENT_VERSION=""
fi

INSTALLED=0

if [ "$VERSION" != "$CURRENT_VERSION" ]; then
	aws s3 cp s3://helium-releases/helium-$SERVICE/$SERVICE-$VERSION-sunos.tgz .

	mkdir -p /opt/helium/$SERVICE

	tar -C /opt/helium/$SERVICE -xf $SERVICE-$VERSION-sunos.tgz

	rm -f /opt/helium/$SERVICE/current

	ln -sf /opt/helium/$SERVICE/$SERVICE-$VERSION/ /opt/helium/$SERVICE/current

	## Run the install hook
	/opt/helium/$SERVICE/current/helios/hooks/install.sh
	INSTALLED=1
fi

## we need to construct the mustache 'data' json from consul/system attributes (eg. IP)
## TODO 'system' variables

HOSTIP=`ifconfig net0 | grep inet | awk '{print $2}'`

echo "{" > ~/data.json

curl -s http://127.0.0.1:8500/v1/kv/$SERVICE/config?recurse=1 | json -a Key Value | awk '{sub(/\w+\/config\//, "", $1)}{"base64 -d<<< \""$2"\""|getline $4}{printf "    \"%s\":%s,\n", $1, $4}' >> ~/data.json

echo "    \"host_ip\": \"$HOSTIP\"" >> ~/data.json
echo "}" >> ~/data.json

CONFIG_VERSION=`shasum  data.json  | awk '{print $1}'`

CONFIGURED=0
if [ "$CURRENT_CONFIG" != "$CONFIG_VERSION" -o $INSTALLED -eq 1 ]; then
	## find all the .mustache files and re-template them
	find /opt/helium/$SERVICE/current/ -name \*.mustache -exec ksh -c '
	  for f; do
	    OUTPUT=`echo $f | sed s/.mustache$//`
	    cat /opt/helium/$SERVICE/current/helios/default.json ~/data.json | json --merge | mustache - $f > $OUTPUT
	  done
	' _ {} +

	## Run the config hook
	/opt/helium/$SERVICE/current/helios/hooks/config.sh
	CONFIGURED=1
fi

## did we do a thing?
if [ $INSTALLED -eq 1 -o $CONFIGURED -eq 1 ]; then
	## do some magic with SMF here, the SMF script should be part of the package, ideally
	svccfg import /opt/helium/$SERVICE/current/helios/smf/$SERVICE.xml
	svcadm enable $SERVICE
	svcadm clear $SERVICE

	SERVICESTATE=`svcs | grep $SERVICE | awk '{ print $1 }'`

	## Register the service
	curl -X PUT -d "{\"Name\": \"$SERVICE\", \"Tags\": [\"version-$VERSION\", \"config-$CONFIG_VERSION\"]}" http://127.0.0.1:8500/v1/agent/service/register

	## install or update any health checks
	## XXX should we worry about deleting old checks, or should we require the set to only ever grow?
	find /opt/helium/$SERVICE/current/helios/checks -name \*.json -exec ksh -c '
	  for f; do
	    curl -s -X PUT -d @$f http://127.0.0.1:8500/v1/agent/check/register
	  done
	' _ {} +
	
		
	## we are going to delete any old sessions and create a new one because the set of checks may have changed
	if [ -z $CURRENT_SESSION ]; then
		curl -s -X PUT http://127.0.0.1:8500/v1/session/destroy/$CURRENT_SESSION
	fi

	if [ $INSTALLED -eq 1 ]; then
		echo "$SERVICE was installed or upgraded"
	else
		echo "$SERVICE was reconfigured"
	fi

	# XXX we do NOT try to acquire a session/become the leader here right now, maybe we should?
else
	#echo "current-session--$CURRENT_SESSION--"
	if [ -z $CURRENT_SESSION ]; then
		echo "creating session"
		## XXX we should be checking these checks are related to $SERVICE
		CHECKS=`curl -s http://127.0.0.1:8500/v1/agent/checks | json -k | head -n -1 | tail -n +2 | awk '{gsub(/(^"|",?$)/, "", $1); printf "\"%s\",", $1}'`
		NEW_SESSION=`curl -s -X PUT -d "{\"lockdelay\": \"0s\", \"checks\": [$CHECKS \"serfHealth\"], \"TTL\": \"120s\", \"name\": \"$SERVICE-leader\"}"  http://127.0.0.1:8500/v1/session/create | json ID`
		if [ $? -eq 0 ]; then
			## try to acquire the lock
			LEADER=`curl -s -X PUT -d $HOSTIP http://localhost:8500/v1/kv/service/$SERVICE/leader?acquire=$NEW_SESSION`
			## store the new session ID
			curl -s -X PUT -d "$NEW_SESSION" http://127.0.0.1:8500/v1/kv/sessions/$ZONENAME/$SERVICE > /dev/null
			echo "leader $LEADER"
		fi
	else
		echo "session renewed"
		## renew the session
		curl -s -X PUT http://127.0.0.1:8500/v1/session/renew/$CURRENT_SESSION > /dev/null
		## try to acquire the lock
		LEADER=`curl -s -X PUT -d $HOSTIP http://localhost:8500/v1/kv/service/$SERVICE/leader?acquire=$CURRENT_SESSION`
		echo "leader $LEADER"
	fi
	echo "$SERVICE is up to date"
fi
