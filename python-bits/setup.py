#!/usr/bin/env python

from setuptools import setup

setup(name='Helios',
      version='1.0',
      description='Helios',
      author='Helium',
      author_email='helium.com',
      url='https://github.com/helium/helios/',
      py_modules=['helios', 'helios_get_service_leader', 'helios_get_service_members', 'helios_zonename_to_ip'],
      install_requires=['python-consul', 'netifaces', 'pystache'],
      entry_points='''
        [console_scripts]
        helios=helios:main
        helios_get_service_leader=helios_get_service_leader:main
        helios_get_service_members=helios_get_service_members:main
        helios_zonename_to_ip=helios_zonename_to_ip:main
      '''
     )
