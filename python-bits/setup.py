#!/usr/bin/env python

from setuptools import setup

setup(name='Helios',
      version='1.0',
      description='Helios',
      author='Helium',
      author_email='helium.com',
      url='https://github.com/helium/helios/',
      py_modules=['example'],
      install_requires=['python-consul', 'netifaces', 'pystache'],
      entry_points='''
        [console_scripts]
        example=example:main
      '''
     )
