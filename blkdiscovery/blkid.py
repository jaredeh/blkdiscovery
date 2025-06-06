import os
import re
from .blkdiscoveryutil import *

class Blkid(BlkDiscoveryUtil):

    def parse_line(self,line):
        details = {}
        diskline = line.split(':',1)
        if len(diskline) < 2:
            return
        path = diskline[0]
        for match in re.finditer('(\S+)\=\"([^\"]+)\"',diskline[1]):
            details[match.group(1)] = match.group(2)
        return path, details

    def find_disks(self,output):
        disklist = []
        blockdevices = []
        for disk in os.listdir("/sys/block"):
            blockdevices.append(f'/dev/{disk}')
        for path, details in output.items():
            if path in blockdevices:
                disklist.append(path)
                continue
            m1 = re.search('(p\d+$)',path)
            m2 = re.search('(\d+$)',path)
            if not m2:
                disklist.append(path)
                continue
            if m1:
                match = m1
            else:
                match = m2
            disk = path.rsplit(match.group(1))[0]
            if disk in disklist:
                continue
            if not disk in blockdevices:
                continue
            disklist.append(disk)
        return disklist

    def details(self):
        retval = {}
        rawdata = self.call_blkid()
        disklist = self.find_disks(rawdata)
        #we need to call blkid with a disk to get the partition info, weird
        for path in disklist:
            output = self.call_blkid(path)
            if not output.get(path):
                continue
            retval[path] = output[path]
        return retval

    def call_blkid(self,device=None):
        retval = {}
        self.subprocess_check_output(["blkid", '-g'])
        cmdarray = ["blkid", '-o', 'full']
        if device:
            cmdarray.append(device)
        rawoutput = self.subprocess_check_output(cmdarray)
        for line in rawoutput.splitlines():
            path, details = self.parse_line(line)
            retval[path] = details
        return self.stringify(retval)

if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    l = Blkid()
    devdata = l.call_blkid()
    pp.pprint(devdata)
    disks = l.find_disks(devdata)
    pp.pprint(disks)
    details = l.details()
    pp.pprint(details)
