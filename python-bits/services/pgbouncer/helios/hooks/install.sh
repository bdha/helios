#!/usr/bin/ksh

svcadm disable pgbouncer
svccfg delete pgbouncer

mkdir /var/pgsql
chown postgres:postgres /var/pgsql

mkdir /var/log/pgbouncer
chown postgres:postgres /var/log/pgbouncer
