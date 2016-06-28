#!/usr/bin/env python
import consul
import sys

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: {0} <zonename>\n".format(sys.argv[0]))
        sys.exit(1)
    zonename = sys.argv[1]
    c = consul.Consul()
    index, services = c.catalog.node(zonename)
    if services:
        print(services['Node']['Address'])
        #sys.stdddout.write("{0}\n".format(data['Value'].decode('utf-8')))
        sys.exit(0)
    sys.exit(2)

if __name__ == '__main__':
    main()
