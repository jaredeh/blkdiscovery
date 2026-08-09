from . import blkid
from . import hdparm
from . import lsblk
from . import lshw
from . import lsstoragecntlr
from . import nvme
import re
from typing import Any, Dict, List, Optional
from .blkdiscoveryutil import LocalRunner, SshRunner
from .types import DatasetConfig, DeviceDetails, DeviceInfo, DiskList, PartitionInfo, create_dataset_configs


# PartitionInfo attribute -> the key lsblk and blkid both report it under
CHILD_FIELDS = {
    'mountpoint': 'mountpoint',
    'size': 'size',
    'partition_table_type': 'PTTYPE',
    'partition_table_UUID': 'PTUUID',
    'format': 'TYPE',
    'partition_UUID': 'PARTUUID',
    'UUID': 'UUID',
    'UUID_SUB': 'UUID_SUB',
}


class BlkDiscovery:

    def __init__(self, host: Optional[str] = None, runner: Optional[Any] = None) -> None:
        """Discover local block devices, or those of `host` when given.

        `runner` overrides both and is the seam for anything else that can run
        a command and read a file.
        """
        self.runner = runner or (SshRunner(host) if host else LocalRunner())
        self.lsblk: lsblk.LsBlk = lsblk.LsBlk(self.runner)
        self.lshw: lshw.LsHw = lshw.LsHw(self.runner)
        self.blkid: blkid.Blkid = blkid.Blkid(self.runner)
        self.lsstoragecntlr: lsstoragecntlr.LsStorageController = lsstoragecntlr.LsStorageController(self.runner)
        self.hdparm: hdparm.Hdparm = hdparm.Hdparm(self.runner)
        self.nvme: nvme.Nvme = nvme.Nvme(self.runner)

    def disks(self) -> DiskList:
        return self.lsblk.disks()

    def consolidate_disk(self, disk: str, device_info: DeviceInfo, dataset_configs: List[DatasetConfig]) -> None:
        """Fill a DeviceInfo from every dataset that has something to say about this disk."""
        for config in dataset_configs:
            for attr, keys in config.keypairs.items():
                if not (value := config.extract_value(disk, keys)):
                    continue
                if isinstance(value, str):
                    if not (value := value.strip()):
                        continue
                    if attr == 'bytes' and value.isdigit():
                        value = int(value)
                setattr(device_info, attr, value)

    def details(self) -> DeviceDetails:
        disks = self.disks()

        # Collect raw data from all sources
        hdparm_data = {disk: self.hdparm.details(disk) for disk in disks}
        lsblk_data = self.lsblk.details()
        blkid_data = self.blkid.details()
        lsstoragecntlr_data = self.lsstoragecntlr.details()
        nvme_data = self.nvme.details()
        dataset_configs = create_dataset_configs(lsblk_data, hdparm_data, lsstoragecntlr_data,
                                                 blkid_data, nvme_data)

        retval: DeviceDetails = {}
        for disk in disks:
            device_info = DeviceInfo()
            self.consolidate_disk(disk, device_info, dataset_configs)

            if disk_lsblk := lsblk_data.get(disk):
                dataset = disk_lsblk
                #going to treat partitionless disks with filesystem as special cases
                #where they are their own children
                if disk_blkid := blkid_data.get(disk):
                    if not disk_blkid.get("PTTYPE") and disk_blkid.get('TYPE'):
                        dataset = {'children': {disk: disk_lsblk}}
                self.process_children(device_info.children, dataset)

            self.scrub_device_info(device_info)
            retval[disk] = device_info

        return retval

    def process_children(self, children: Dict[str, PartitionInfo], dataset: Dict[str, Any]) -> None:
        """Populate `children` with the partitions of `dataset`, recursing into stacked devices."""
        for name, child_data in dataset.get('children', {}).items():
            #blkid only reports partition details when called with the partition, weird
            child_blkid = self.blkid.call_blkid(name).get(name, {})
            attrs = {}
            for attr, key in CHILD_FIELDS.items():
                for source in (child_data, child_blkid):
                    if not (value := source.get(key)):
                        continue
                    if isinstance(value, str):
                        value = value.strip()
                    if attr == 'mountpoint' and value == 'None':
                        continue
                    attrs[attr] = value
            partition = PartitionInfo(**attrs)
            children[name] = partition
            self.process_children(partition.children, child_data)

    def scrub_device_info(self, device_info: DeviceInfo) -> None:
        """Clean up and normalize device information."""
        if device_info.disk_class and re.search('SATA', device_info.disk_class):
            device_info.disk_class = 'SATA'

        if device_info.storage_bus:
            device_info.storage_bus = device_info.storage_bus.upper()

        device_info.mounted = device_info.is_mounted()
