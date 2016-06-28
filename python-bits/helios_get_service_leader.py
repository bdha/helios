#!/usr/bin/env python
import consul
import sys

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: {0} <service>\n".format(sys.argv[0]))
        sys.exit(1)
    service = sys.argv[1]
    c = consul.Consul()
    index, data = c.kv.get("service/{0}/leader".format(service))
    if data:
        sys.stdout.write("{0}\n".format(data['Value'].decode('utf-8')))
        sys.exit(0)
    sys.exit(2)

if __name__ == '__main__':
    main()
