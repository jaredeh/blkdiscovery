"""Type definitions for blkdiscovery."""

from typing import Dict, List, Optional, Union, TypedDict


class DeviceInfo(TypedDict, total=False):
    """Device information structure."""
    model: str
    vendor: str
    serial: str
    firmware: str
    disk_class: str
    WWN: str
    bytes: int
    size: str
    storage_controller: str
    storage_path: str
    storage_bus: str
    linux_subsystems: str
    linux_scheduler: str
    minimum_IO: str
    partition_table_type: str
    partition_table_UUID: str
    mounted: bool
    children: Dict[str, 'PartitionInfo']


class PartitionInfo(TypedDict, total=False):
    """Partition information structure."""
    mountpoint: str
    size: str
    partition_table_type: str
    partition_table_UUID: str
    format: str
    partition_UUID: str
    UUID: str
    UUID_SUB: str


class DatasetKeyPair(TypedDict):
    """Dataset and keypair mapping structure."""
    dataset: Dict[str, Dict[str, Union[str, int, Dict]]]
    keypairs: Dict[str, List[str]]


# Type aliases
DeviceDetails = Dict[str, DeviceInfo]
DiskList = List[str]
