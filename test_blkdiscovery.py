#!/usr/bin/env python3
"""Self-check for the dataset -> dataclass -> JSON pipeline. Run: python3 test_blkdiscovery.py"""

import json
import subprocess
from dataclasses import fields

from blkdiscovery.blkdiscovery import BlkDiscovery
from blkdiscovery.blkdiscoveryutil import LocalRunner, SshRunner
from blkdiscovery.lsstoragecntlr import LsStorageController
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


def test_pcie_link():
    """The endpoint is the innermost PCI address, not the root port above it."""
    sysfs = {
        '/sys/block/nvme0n1': '/sys/devices/pci0000:00/0000:00:01.1/0000:01:00.0/nvme/nvme0/nvme0n1',
        '/sys/block/sda': '/sys/devices/pci0000:00/0000:00:01.3/0000:02:00.1/ata2/host1/block/sda',
        '/sys/block/dm-0': '/sys/devices/virtual/block/dm-0',
        '/sys/bus/pci/devices/0000:01:00.0/current_link_speed': '8.0 GT/s PCIe',
        '/sys/bus/pci/devices/0000:01:00.0/current_link_width': '4',
        '/sys/bus/pci/devices/0000:01:00.0/max_link_speed': '16.0 GT/s PCIe',
        '/sys/bus/pci/devices/0000:01:00.0/max_link_width': '4',
        '/sys/bus/pci/devices/0000:02:00.1/current_link_speed': 'Unknown speed',
    }

    class SysfsRunner:
        read_file = staticmethod(sysfs.get)
        realpath = staticmethod(sysfs.get)

    lsc = LsStorageController(SysfsRunner())
    assert lsc.pci_address('nvme0n1') == '0000:01:00.0'   # endpoint, not 0000:00:01.1
    assert lsc.pci_address('dm-0') is None                # virtual device, no PCI at all

    details = {}
    lsc.get_pcie_link('nvme0n1', details)
    assert details == {'PCIe link speed': '8.0 GT/s PCIe', 'PCIe link width': '4',
                       'PCIe max link speed': '16.0 GT/s PCIe', 'PCIe max link width': '4'}

    #a downtrained Gen4 drive reads Gen3 right now, so max is what makes it readable
    assert details['PCIe link speed'] != details['PCIe max link speed']

    details = {}
    lsc.get_pcie_link('sda', details)
    assert details == {}  # "Unknown speed" is not a speed
    lsc.get_pcie_link('dm-0', details)
    assert details == {}


def test_ssh_command():
    runner = SshRunner('root@box', ssh_options=['-o', 'BatchMode=yes'])
    assert runner.ssh_command(['hdparm', '-I', '/dev/sd a']) == [
        'ssh', '-o', 'BatchMode=yes', 'root@box', "sudo -n hdparm -I '/dev/sd a'"]
    assert SshRunner('box', sudo=False, ssh_options=[]).ssh_command(['lspci']) == [
        'ssh', 'box', 'lspci']
    #a dead host must degrade to "" the same way a missing local binary does
    assert SshRunner('box', ssh_options=['-o', 'BatchMode=yes',
                                         '-o', 'ProxyCommand=false']).run(['lspci']) == ""


class ShellRunner(SshRunner):
    """SshRunner with the ssh+sudo hop removed, so its remote shell commands run here.

    Lets the shell-based sysfs emulation be checked against the real thing
    without needing a second machine.
    """

    def __init__(self):
        super().__init__('unused')

    def run(self, cmdarray):
        remote = self.ssh_command(cmdarray)[-1].replace('sudo -n ', '', 1)
        try:
            return subprocess.check_output(['sh', '-c', remote],
                                           stderr=subprocess.DEVNULL).decode()
        except Exception:
            return ""


def test_remote_filesystem_matches_local():
    """cat/ls/readlink must answer what open/listdir/realpath answer."""
    local, remote = LocalRunner(), ShellRunner()

    assert remote.isdir('/sys/block') is True
    assert remote.isdir('/sys/block/definitely-not-here') is False
    assert sorted(remote.listdir('/sys/block')) == sorted(local.listdir('/sys/block'))
    assert remote.listdir('/sys/block/definitely-not-here') == []
    assert remote.realpath('/sys/block') == local.realpath('/sys/block')

    disk = sorted(local.listdir('/sys/block'))[0]
    path = f'/sys/block/{disk}/size'
    assert remote.read_file(path) == local.read_file(path) != None
    assert remote.read_file('/sys/block/definitely-not-here') is None
    assert remote.run(['lsblk', '--json', '-O', '-p'])  # argv survives the quoting


def test_unreachable_host_is_empty_not_a_traceback():
    class DeadRunner:
        run = staticmethod(lambda cmdarray: "")
        read_file = staticmethod(lambda path: None)
        listdir = staticmethod(lambda path: [])
        realpath = staticmethod(lambda path: None)
        isdir = staticmethod(lambda path: False)

    assert BlkDiscovery(runner=DeadRunner()).details() == {}


def test_runner_is_the_only_way_out():
    """Every disk fact must arrive through the runner, or --host silently reports local data."""
    lsblk = {'blockdevices': [{'name': '/dev/sda', 'type': 'disk', 'tran': 'sata',
                               'children': [{'name': '/dev/sda1', 'mountpoint': '/mnt'}]}]}

    class FakeRunner:
        def __init__(self):
            self.commands = []

        def run(self, cmdarray):
            self.commands.append(cmdarray[0])
            if cmdarray[0] == 'lsblk':
                return json.dumps(lsblk)
            if cmdarray[0] == 'blkid':
                return '/dev/sda: PTTYPE="gpt"\n/dev/sda1: TYPE="ext4"\n'
            return ""

        def read_file(self, path):
            return None

        def listdir(self, path):
            return ['sda'] if path == '/sys/block' else []

        def realpath(self, path):
            return path

        def isdir(self, path):
            return True

    runner = FakeRunner()
    details = BlkDiscovery(runner=runner).details()

    assert list(details) == ['/dev/sda'], details
    sda = details['/dev/sda'].to_dict()
    assert sda['storage bus'] == 'SATA', sda
    assert sda['partition table type'] == 'gpt', sda
    assert sda['mounted'] is True, sda
    assert sda['children']['/dev/sda1']['format'] == 'ext4', sda
    #the nvme/lsstoragecntlr sysfs walks went through the runner too, not os.listdir
    assert 'hdparm' in runner.commands and 'lspci' in runner.commands


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print(f'ok  {name}')
