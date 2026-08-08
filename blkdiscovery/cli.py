#!/usr/bin/env python

import json
from .blkdiscovery import BlkDiscovery


def main() -> None:
    """Main CLI entry point for blkdiscovery."""
    devdata = BlkDiscovery().details()
    print(json.dumps({disk: info.to_dict() for disk, info in devdata.items()}, indent=4))


if __name__ == "__main__":
    main()
