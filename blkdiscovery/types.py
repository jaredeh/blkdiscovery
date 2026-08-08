"""Type definitions for blkdiscovery."""

from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional


def _json_key(name: str) -> str:
    """Attribute name to output key ('disk_class' -> 'disk class')."""
    return name if name == 'UUID_SUB' else name.replace('_', ' ')


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Dataclass to plain dict, dropping unset fields and restoring output key names."""
    result: Dict[str, Any] = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if value is None or value == {}:
            continue
        if f.name == 'children':
            value = {name: _to_dict(child) for name, child in value.items()}
        result[_json_key(f.name)] = value
    return result


@dataclass
class PartitionInfo:
    """Partition information structure."""
    mountpoint: Optional[str] = None
    size: Optional[str] = None
    partition_table_type: Optional[str] = None
    partition_table_UUID: Optional[str] = None
    format: Optional[str] = None
    partition_UUID: Optional[str] = None
    UUID: Optional[str] = None
    UUID_SUB: Optional[str] = None
    children: Dict[str, 'PartitionInfo'] = field(default_factory=dict)

    def is_mounted(self) -> bool:
        """Check if this partition, or anything stacked on it, is mounted."""
        if self.mountpoint and self.mountpoint != 'None':
            return True
        return any(child.is_mounted() for child in self.children.values())

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)


@dataclass
class DeviceInfo:
    """Device information structure."""
    model: Optional[str] = None
    vendor: Optional[str] = None
    serial: Optional[str] = None
    firmware: Optional[str] = None
    disk_class: Optional[str] = None
    WWN: Optional[str] = None
    bytes: Optional[int] = None
    size: Optional[str] = None
    storage_controller: Optional[str] = None
    storage_path: Optional[str] = None
    storage_bus: Optional[str] = None
    linux_subsystems: Optional[str] = None
    linux_scheduler: Optional[str] = None
    minimum_IO: Optional[str] = None
    partition_table_type: Optional[str] = None
    partition_table_UUID: Optional[str] = None
    fabric: Optional[Dict[str, str]] = None
    mounted: bool = False
    children: Dict[str, PartitionInfo] = field(default_factory=dict)

    def is_mounted(self) -> bool:
        """Check if the device or any of its partitions are mounted."""
        return self.mounted or any(child.is_mounted() for child in self.children.values())

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)


@dataclass
class DatasetConfig:
    """A raw tool dataset plus the DeviceInfo attribute -> key path map to pull from it."""
    dataset: Dict[str, Dict[str, Any]]
    keypairs: Dict[str, List[str]]

    def extract_value(self, disk: str, keys: List[str]) -> Any:
        """Walk the key path for one disk, or None if any step is missing."""
        if not (data := self.dataset.get(disk)):
            return None

        for key in keys:
            if not isinstance(data, dict) or not (data := data.get(key)):
                return None
        return data


def create_dataset_configs(lsblk: Dict, hdparm: Dict, lsstoragecntlr: Dict,
                           blkid: Dict, nvme: Dict) -> List[DatasetConfig]:
    """Create standardized dataset configurations.

    Order matters: later configs overwrite earlier ones for the same attribute.
    """
    return [
        DatasetConfig(
            dataset=lsblk,
            keypairs={
                'linux_subsystems': ['subsystems'],
                'linux_scheduler': ['sched'],
                'storage_bus': ['tran'],
                'minimum_IO': ['min-io'],
                'model': ['model'],
                'vendor': ['vendor'],
                'serial': ['serial'],
                'firmware': ['rev'],
                'size': ['size'],
            }
        ),
        DatasetConfig(
            dataset=hdparm,
            keypairs={
                'model': ['Device', 'Model Number'],
                'vendor': ['Device', 'Vendor'],
                'serial': ['Device', 'Serial Number'],
                'firmware': ['Device', 'Firmware Revision'],
                'disk_class': ['Device', 'Transport'],
                'WWN': ['Device', 'Logical Unit WWN Device Identifier'],
                'bytes': ['Configuration', 'Disk Size', 'bytes'],
                'size': ['Configuration', 'Disk Size', 'human base10'],
            }
        ),
        DatasetConfig(
            dataset=lsstoragecntlr,
            keypairs={
                'storage_controller': ['controller'],
                'storage_path': ['storagepath'],
            }
        ),
        DatasetConfig(
            dataset=blkid,
            keypairs={
                'partition_table_type': ['PTTYPE'],
                'partition_table_UUID': ['PTUUID'],
            }
        ),
        DatasetConfig(
            dataset=nvme,
            keypairs={
                'disk_class': ['disk class'],
                'storage_controller': ['storage controller'],
                'storage_path': ['storage path'],
                'model': ['model'],
                'serial': ['serial'],
                'firmware': ['firmware'],
                'WWN': ['WWN'],
                'bytes': ['bytes'],
                'size': ['size'],
                'fabric': ['fabric'],
            }
        ),
    ]


# Type aliases
DeviceDetails = Dict[str, DeviceInfo]
DiskList = List[str]
