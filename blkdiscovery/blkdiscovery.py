from . import blkid
from . import hdparm
from . import lsblk
from . import lshw
from . import lsstoragecntlr
import re


class BlkDiscovery:

    def __init__(self):
        self.lsblk = lsblk.LsBlk()
        self.lshw = lshw.LsHw()
        self.blkid = blkid.Blkid()
        self.lsstoragecntlr = lsstoragecntlr.LsStorageController()
        self.hdparm = hdparm.Hdparm()

    def disks(self):
        return self.lsblk.disks()

    def extract_value(self,dataset,disk,keylist):
        if not dataset.get(disk):
            return None
        data = dataset[disk]
        keys = list(keylist)
        for i in range(len(keys)):
            key = keys.pop(0)
            if not data.get(key):
                return None
            data = data[key]
            if len(keys) == 0:
                return data


    def find_children(self,disk,retval,keypairs,dataset):
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
                    if type(value) == str:
                        value = value.strip()
                    if not (newkey == 'mountpoint' and value == 'None'):
                        retval['children'][child][newkey] = value
                blkid = self.blkid.call_blkid(child)
                value = self.extract_value(blkid,child,keys)
                if value:
                    if type(value) == str:
                        value = value.strip()
                    retval['children'][child][newkey] = value
            self.find_children(child,retval['children'][child],keypairs,dataset['children'][child])
        return

    def consolidate_disk(self,disk,retval,datasetkeypairs):
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
                    if type(value) == str:
                        value = value.strip()
                    retval[newkey] = value

    def details(self):
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

    def check_if_mounted(self,parent):
        if parent.get('mountpoint'):
            return True
        if not parent.get('children'):
            return False
        for child, details in parent['children'].items():
            if self.check_if_mounted(details):
                return True
        return False

    def scrub(self,retval):
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
