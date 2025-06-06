from . import blkid
from . import hdparm
from . import lsblk
from . import lshw
from . import lsstoragecntlr
import re
from typing import Dict, List, Optional, Any, Union
from .types import DeviceDetails, DiskList, DatasetKeyPair


class BlkDiscovery:

    def __init__(self) -> None:
        self.lsblk: lsblk.LsBlk = lsblk.LsBlk()
        self.lshw: lshw.LsHw = lshw.LsHw()
        self.blkid: blkid.Blkid = blkid.Blkid()
        self.lsstoragecntlr: lsstoragecntlr.LsStorageController = lsstoragecntlr.LsStorageController()
        self.hdparm: hdparm.Hdparm = hdparm.Hdparm()

    def disks(self) -> DiskList:
        return self.lsblk.disks()

    def extract_value(self, dataset: Dict[str, Any], disk: str, keylist: List[str]) -> Optional[str]:
        if not (data := dataset.get(disk)):
            return None

        for key in keylist:
            if not (data := data.get(key)):
                return None
        return data


    def find_children(self, disk: str, retval: Dict[str, Any], keypairs: Dict[str, List[str]], dataset: Dict[str, Any]) -> None:
        if not dataset.get('children'):
            return
        if not retval.get('children'):
            retval['children'] = {}
        for child in dataset['children']:
            if not retval['children'].get(child):
                retval['children'][child] = {}
            for newkey, keys in keypairs.items():
                value = self.extract_value(dataset['children'],child,keys)
                if value:
                    if isinstance(value, str):
                        value = value.strip()
                    if not (newkey == 'mountpoint' and value == 'None'):
                        retval['children'][child][newkey] = value
                blkid = self.blkid.call_blkid(child)
                value = self.extract_value(blkid,child,keys)
                if value:
                    if isinstance(value, str):
                        value = value.strip()
                    retval['children'][child][newkey] = value
            self.find_children(child,retval['children'][child],keypairs,dataset['children'][child])
        return

    def consolidate_disk(self, disk: str, retval: Dict[str, Any], datasetkeypairs: List[DatasetKeyPair]) -> None:
        for datasetkeypair in datasetkeypairs:
            if not datasetkeypair.get('dataset'):
                raise ValueError("Missing required 'dataset' key in datasetkeypair")
            if not datasetkeypair.get('keypairs'):
                raise ValueError("Missing required 'keypairs' key in datasetkeypair")
            dataset = datasetkeypair['dataset']
            keypairs =  datasetkeypair['keypairs']
            for newkey, keys in keypairs.items():
                value = self.extract_value(dataset,disk,keys)
                if value:
                    if isinstance(value, str):
                        value = value.strip()
                    retval[newkey] = value

    def details(self) -> DeviceDetails:
        retval = {}
        disks = self.disks()
        hdparm = {}
        for disk in disks:
            hdparm[disk] = self.hdparm.details(disk)
        lsblk = self.lsblk.details()
        lshw = self.lshw.details()
        blkid = self.blkid.details()
        lsstoragecntlr = self.lsstoragecntlr.details()
        diskkeypairs = [
            {'dataset': lsblk,
             'keypairs': {
                'linux subsystems': ['subsystems'],
                'linux scheduler':  ['sched'],
                'storage bus':      ['tran'],
                'minimum IO':       ['min-io'],
                'model':            ['model'],
                'vendor':           ['vendor'],
                'serial':           ['serial'],
                'firmware':         ['rev'],
                }
            },
            {'dataset': hdparm,
             'keypairs': {
                'model':      ['Device','Model Number'],
                'vendor':     ['Device','Vendor'],
                'serial':     ['Device','Serial Number'],
                'firmware':   ['Device','Firmware Revision'],
                'disk class': ['Device','Transport'],
                'WWN':        ['Device','Logical Unit WWN Device Identifier'],
                'bytes':      ['Configuration','Disk Size','bytes'],
                'size':       ['Configuration','Disk Size','human base10']
                }
            },
            {'dataset': lsstoragecntlr,
             'keypairs': {
                'storage controller': ['controller'],
                'storage path':       ['storagepath'],
                }
            },
            {'dataset': blkid,
             'keypairs': {
                'partition table type': ['PTTYPE'],
                'partition table UUID': ['PTUUID'],
                }
            },
        ]
        childkeypairs = {
                'mountpoint':           ['mountpoint'],
                'size':                 ['size'],
                'partition table type': ['PTTYPE'],
                'partition table UUID': ['PTUUID'],
                'format':               ['TYPE'],
                'partition UUID':       ['PARTUUID'],
                'UUID':                 ['UUID'],
                'UUID_SUB':             ['UUID_SUB'],

        }
        for disk in disks:
            if not retval.get(disk):
                retval[disk] = {}
            self.consolidate_disk(disk,retval[disk],diskkeypairs)
            if not lsblk.get(disk):
                continue
            dataset = lsblk[disk]
            #going to treat partitionless disks with filesystem as special cases
            #where they are their own children
            if blkid.get(disk):
                if not blkid[disk].get("PTTYPE") and blkid[disk].get('TYPE'):
                    dataset = {'children': {disk: lsblk[disk]}}
            self.find_children(disk,retval[disk],childkeypairs,dataset)
        self.scrub(retval)
        return retval

    def check_if_mounted(self, parent: Dict[str, Any]) -> bool:
        if parent.get('mountpoint'):
            return True
        if not parent.get('children'):
            return False
        for child, details in parent['children'].items():
            if self.check_if_mounted(details):
                return True
        return False

    def scrub(self, retval: Dict[str, Dict[str, Any]]) -> None:
        for disk, details in retval.items():
            if details.get('disk class'):
                if re.search('SATA',details['disk class']):
                    details['disk class'] = 'SATA'
            if details.get('storage bus'):
                details['storage bus'] = details['storage bus'].upper()
            if self.check_if_mounted(details):
                details['mounted'] = True
            else:
                details['mounted'] = False
