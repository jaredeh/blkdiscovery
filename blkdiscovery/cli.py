#!/usr/bin/env python

import json
from .blkdiscovery import BlkDiscovery


def main() -> None:
    """Main CLI entry point for blkdiscovery."""
    bd = BlkDiscovery()
    disks = bd.disks()
    devdata = bd.details()
    print(json.dumps(devdata, indent=4))


if __name__ == "__main__":
    main()
