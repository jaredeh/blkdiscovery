#!/usr/bin/env python

import pprint
from .blkdiscovery import BlkDiscovery


def main():
    """Main CLI entry point for blkdiscovery."""
    pp = pprint.PrettyPrinter(indent=4)
    bd = BlkDiscovery()
    disks = bd.disks()
    pp.pprint(disks)
    devdata = bd.details()
    pp.pprint(devdata)


if __name__ == "__main__":
    main()
