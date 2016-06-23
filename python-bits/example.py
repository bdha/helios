#!/usr/bin/env python
import consul

def main():
    c = consul.Consul()

    # poll a key for updates
    index = None
    while True:
        index, data = c.kv.get('foo', index=index)
        print data['Value']

if __name__ == '__main__':
    main()
