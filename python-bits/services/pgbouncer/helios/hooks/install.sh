#!/usr/bin/ksh

svcadm disable pgbouncer
svccfg delete pgbouncer

mkdir /var/pgsql
chown postgres:postgres /var/pgsql

mkdir /var/log/postgresql
chown postgres:postgres /var/log/postgresql

mkdir /var/run/postgresql
chown postgres:postgres /var/run/postgresql
