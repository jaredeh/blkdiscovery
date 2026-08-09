#!/usr/bin/env python

import argparse
import json
import sys
from .blkdiscovery import BlkDiscovery


def main() -> None:
    """Main CLI entry point for blkdiscovery."""
    parser = argparse.ArgumentParser(description="Find block devices and extract details from Linux")
    parser.add_argument('--host', help="discover a remote machine over ssh ([user@]host), "
                                       "using passwordless sudo there")
    args = parser.parse_args()

    devdata = BlkDiscovery(host=args.host).details()
    if not devdata:
        #every tool failing looks like "no disks", so say so instead of printing {}
        sys.exit(f"blkdiscovery: found no block devices on {args.host or 'this machine'} "
                 "(reachable? lsblk installed? running as root?)")
    print(json.dumps({disk: info.to_dict() for disk, info in devdata.items()}, indent=4))


if __name__ == "__main__":
    main()
