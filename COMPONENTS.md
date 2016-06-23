## Consul server

Core KV store. Performs healthchecks, leader elections, stores config data and service registry.

Initial Consul load-out can (?) be defined in a JSON blob.

Each environment has its own Consul cluster.

## Consul agent

Runs on each node. All Consul traffic goes through the local agent. Manages sessions, etc.

### Service registry

Allows a node with a role to lookup where to find its initial download path, amongst (presumably) other things.

```
helios-service-registry {
  router {
    url: ...
  },
  graf {
    url: ...
  },
  ...
}
```

## heliosadm

Management CLI tool.

* manage service registry (eventually calls helios-api)

## helios-api

API service that drives Consul and other useful things.

Uses Helium/Pilgrim API keys for auth.

As time goes on, less adm traffic goes directly to Consul, more through api.

## helios-agent

Runs on each helios-ified node. Talks to Consul/helios-api to configure itself and the node it's running on.

### Workflow

## helios service definition

Directory structure within a given tarball that defines how the service should be configured, managed, upgraded, and monitored.

## pilgrim

Helium admin CLI tool. Talks to helios-api.
