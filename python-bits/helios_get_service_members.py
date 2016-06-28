#!/usr/bin/env python
import consul
import sys

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: {0} [--json] <service>\n".format(sys.argv[0]))
        sys.exit(1)
    jsonmode = False
    if len(sys.argv) == 3:
        if sys.argv[1] == '--json':
            jsonmode = True
            service = sys.argv[2]
        else:
            sys.stderr.write("Usage: {0} [--json] <service>\n".format(sys.argv[0]))
            sys.exit(1)
    else:
        service = sys.argv[1]
    c = consul.Consul()
    index, nodes = c.health.service(service, passing=True)
    if len(nodes) < 1:
        sys.exit(2)
    acc = []
    for node in nodes:
        acc.append(node['Node']['Address'])
    if jsonmode:
        sys.stdout.write("[\"{0}\"]\n".format("\", \"".join(acc)))
    else:
        sys.stdout.write("{0}\n".format(" ".join(acc)))
    sys.exit(0)

if __name__ == '__main__':
    main()
