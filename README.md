Introduction
------------

Helios is a deployment system for Helium, it takes ideas from Chef, ContainerPilot and Habitat, throws away all the portability (ContainerPilot and Habitat don't support SmartOS anyway) and goes all in on SmartOS/SMF and Consul. It is written in POSIX SH and currently is less than 300 lines of code.

Why?
---

We built this because we were frustrated with Chef, deploys are complicated and
hard, information about how an application runs lives in 2 places (the
application's repo and in Chef), config management is a bit of a pain and
there's no support for health checks/leader election/automated failover.

Both ContainerPilot and Habitat address pieces of these problems, but neither is
entirely what we wanted. Additionally, they are both written in 'trendy' new
languages like Go and Rust and both did not work out of the box on SmartOS (and
the porting work looked non-trivial).

Consul, despite being written in Go, *does* work on SmartOS and it has many of
the features we need already. Helios is just the glue between SmartOS and
Consul.

How it works
------------

Consul has many aspects, it has a key/value store, but it also has the concept
of 'nodes', 'services', 'checks' and 'sessions'.

Nodes are a machine, in this case they represent a SmartOS zone. Services
represent the service that runs on a Node (eg. Router, API, etc). Services can
have health checks associated with them, that consul will run periodically to
check the health of a service and the node it runs on. Sessions are sort of like
distributed locks, which you can tie to the health of a service. If the service
becomes unhealthy, your session becomes invalid. Sessions can be used to hold a
lock on a key/value key, so as long as the session is healthy and you've won the
election, you can hold your lock on the key.

Helios uses all of the above pieces (consul has other features we don't use) to
operate.

The first thing helios does, when a new zone is created, is to configure what
service runs on that zone. This is stored in the k/v store associated with the
SmartOS `zonename` (basicially a uuid). Thus when the new zone comes up, the
bundled helios client (part of the image) figures out what service it should be
running (and the version). It downloads that package from s3, extracts it to
/opt/helium/$SERVICE and sets up the /opt/helium/$SERVICE/current symlink, just like
chef does today.

Next, helios runs the 'install' hook, which is part of the package (so it can
change over time). This hook is used to install dependancies, run migrations,
add users, etc, and should be idempotent as it is also run for upgrades.

Then, helios uses a combination of a `default.json` from the package and any
overidden config from Consul to template any .mustache files in the package.
This is commonly used for configuration variables, but can be used to template
ANY file in the package ending in .mustache.

If the configuration in Consul changes, helios notices and will re-template
files and run the 'config' hook, which is used to tell the application how to
respond to a configuaration change (eg restart or SIGHUP).

Additionally, helios will look for 'health checks' in the package, and install
them into the service inside consul. Health checks can be scripts, HTTP URLs to hit, or TCP
ports to attempt to connect to. See the consul documentation for more details
here.

Then, using the configured checks, helios will obtain a consul session and try
to lock a 'leader' key. Helios runs periodically from cron, and so will renew
the session over time, and thus remain the leader (if elected). If helios stops
running, or if the health checks start failing, an election will be held.

The election is currently non-binding, but the result could be used by haproxy
for routing, or for something like 'what node in the cluster should I join'. The
health of all the instances of a service can also be examined, so things that
don't need a leader can still take bad nodes out of service, etc.

How to make an application work with Helios
-------------------------------------------

I (Andrew) have ported router to work with helios, on a branch called `experiment/helios`. The additions are pretty simple, we have 2 .mustache versions of the config files: https://github.com/helium/router/blob/experiment/helios/config/sys.config.mustache and https://github.com/helium/router/blob/experiment/helios/config/vm.args.mustache that we add to the package.

We also have a `helios` directory that is added to the package root:

https://github.com/helium/router/tree/experiment/helios/helios

The `default.json` is where you put all the default values for your templates (if they don't exist in either default.json or in Consul they end up blank in the config file, which is usually not what you want). Any of these variables can be overridden by setting them in Consul.

The `smf` folder contains the SMF definition and the run script (that the SMF definition references). Every time the package is upgraded, the new SMF definition is re-imported.

`hooks` contains the 2 currently implemented hooks, the `install` and `config` hooks. More of these are planned, just not implemented yet.

`checks` contains the consul check definitions. Router has 3, one script, one HTTP and one TCP. You can actually see that some of these files are templated because they rely on the configuration variables for port assignments. For more detail on the consul check syntax, see https://www.consul.io/docs/agent/checks.html

Helios Commands
---------------

Helios is just a big bag of undocumented shell scripts right now, here's a quick walkthrough.

Right now, helios can't spin a zone itself, it requires you spin a zone, bootstrap helios on there (also not documented).

Once you have a zone that can run helios (we will bake helios into an image once it is ready, so this won't be necessary), you need to configure what version of a package you want to run in this environment:

```
./set_version.sh router 1e3eb0a
```

This will make all `router` zones in this environment (staging, prod, whatever) run this version of router.

Then, once we spin a zone, we cal tell it we want it to be a router:


```
./add_zone.sh router ba1c9447-1b0e-4649-edd5-88bd887da1e1
```

This tells the zone with that uuid that it will be running router. This command will block until the zone has actually come up and deployed the service.

Because we don't have helios integrated into cron yet, you can run the helios client on the new zone

```
./client.sh
```

This will do all the steps noted above in the `how it works` section above. It exits once it is done.

There's 3 scripts for managing the config

```
./set_config.sh <service> <varname> <value>
./delete_config.sh <service> <varname>
./show_config <service>
```


