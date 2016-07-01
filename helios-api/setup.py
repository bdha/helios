#!/usr/bin/env python

from setuptools import setup

setup(name='Helios',
      version='1.0',
      description='Helios',
      author='Helium',
      author_email='helium.com',
      url='https://github.com/helium/helios-api/',
      py_modules=['helios'],
      install_requires=['python-consul', 'flask-restful', 'prettytable' ]
     )
