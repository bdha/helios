#!/usr/bin/ksh

SHA=`git rev-parse --short HEAD`

cd services
SERVICES=`find * -maxdepth 0 -type d`
echo $SERVICES
for SERVICE in $SERVICES; do
    echo $SERVICE
		tar -cf $SERVICE-$SHA-sunos.tgz --transform "s/^$SERVICE/$SERVICE-$SHA/"  $SERVICE
done
