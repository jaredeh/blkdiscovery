#!/usr/bin/env python3
"""Self-check for the dataset -> dataclass -> JSON pipeline. Run: python3 test_blkdiscovery.py"""

from dataclasses import fields

from blkdiscovery.blkdiscovery import BlkDiscovery
from blkdiscovery.types import DeviceInfo, PartitionInfo, create_dataset_configs


def test_keypairs_name_real_fields():
    """consolidate_disk setattr()s these blind, so a typo would silently invent an attribute."""
    valid = {f.name for f in fields(DeviceInfo)}
    for config in create_dataset_configs({}, {}, {}, {}, {}):
        for attr in config.keypairs:
            assert attr in valid, f"{attr} is not a DeviceInfo field"


def test_consolidate_disk():
    lsblk = {'/dev/sda': {'tran': 'sata ', 'model': ' Fake Disk ', 'min-io': '512'}}
    hdparm = {'/dev/sda': {'Configuration': {'Disk Size': {'bytes': '1024', 'human base10': '1 KB'}},
                           'Device': {'Transport': 'Serial, SATA Rev 3.0'}}}
    nvme = {'/dev/nvme0n1': {'disk class': 'NVMe-oF (tcp)', 'fabric': {'transport': 'tcp'}}}
    bd = BlkDiscovery.__new__(BlkDiscovery)

    sda = DeviceInfo()
    bd.consolidate_disk('/dev/sda', sda, create_dataset_configs(lsblk, hdparm, {}, {}, nvme))
    bd.scrub_device_info(sda)
    assert sda.model == 'Fake Disk', sda.model          # stripped
    assert sda.bytes == 1024, sda.bytes                 # coerced to int
    assert sda.size == '1 KB', sda.size                 # hdparm wins over lsblk
    assert sda.storage_bus == 'SATA', sda.storage_bus   # uppercased
    assert sda.disk_class == 'SATA', sda.disk_class     # normalized
    assert sda.mounted is False

    nvme0 = DeviceInfo()
    bd.consolidate_disk('/dev/nvme0n1', nvme0, create_dataset_configs(lsblk, hdparm, {}, {}, nvme))
    assert nvme0.fabric == {'transport': 'tcp'}, nvme0.fabric  # dict survives intact


def test_process_children():
    bd = BlkDiscovery.__new__(BlkDiscovery)
    blkid = {'/dev/sda1': {'/dev/sda1': {'TYPE': 'ext4', 'PARTUUID': 'part-1'}},
             '/dev/sda2': {'/dev/sda2': {'TYPE': 'crypto_LUKS'}},
             '/dev/mapper/vg': {}}
    bd.blkid = type('FakeBlkid', (), {'call_blkid': lambda self, dev: blkid.get(dev, {})})()

    dataset = {'children': {
        '/dev/sda1': {'mountpoint': '/boot ', 'size': '512M', 'TYPE': 'vfat'},
        '/dev/sda2': {'mountpoint': 'None', 'children': {
            '/dev/mapper/vg': {'mountpoint': '/', 'size': '100G'}}},
    }}
    device = DeviceInfo()
    bd.process_children(device.children, dataset)
    bd.scrub_device_info(device)

    sda1 = device.children['/dev/sda1']
    assert sda1.mountpoint == '/boot', sda1.mountpoint  # stripped
    assert sda1.format == 'ext4', sda1.format           # blkid overrides lsblk's vfat
    assert sda1.partition_UUID == 'part-1'
    assert device.children['/dev/sda2'].mountpoint is None  # literal 'None' dropped
    assert device.children['/dev/sda2'].children['/dev/mapper/vg'].mountpoint == '/'  # nesting kept
    assert device.mounted is True  # propagates up from a nested child


def test_to_dict():
    device = DeviceInfo(disk_class='SATA', minimum_IO='512', bytes=1024, mounted=False,
                        children={'/dev/sda1': PartitionInfo(UUID_SUB='sub', mountpoint='/')})
    assert device.to_dict() == {
        'disk class': 'SATA',
        'bytes': 1024,
        'minimum IO': '512',
        'mounted': False,
        'children': {'/dev/sda1': {'mountpoint': '/', 'UUID_SUB': 'sub'}},
    }
    assert PartitionInfo().to_dict() == {}  # unset fields dropped, no empty children key


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print(f'ok  {name}')
