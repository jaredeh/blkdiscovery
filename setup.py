#!/usr/bin/env python

from distutils.core import setup

setup(
    name = 'blkdiscovery',
    version = '0.0.2',
    description = 'Finds block devices and extracts lots of details from Linux',
    license = 'MIT',
    maintainer = 'Jared Hulbert',
    maintainer_email = 'jaredeh@gmail.com',
    url = 'https://github.com/jaredeh/blkdiscovery.git',
    packages = ['blkdiscovery'],
    scripts = ['scripts/blkdiscovery'],
    )
