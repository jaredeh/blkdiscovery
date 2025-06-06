import json
from .blkdiscoveryutil import *

class LsBlk(BlkDiscoveryUtil):

    def disks(self):
        retval = []
        parent = self.details()
        for path, diskdetails in parent.items():
            if not diskdetails.get('type') == "disk":
                continue
            retval.append(path)
        return retval

    def label_children(self,retval):
        if not retval.get('children'):
            return
        children = {}
        for child in retval['children']:
            self.label_children(child)
            if child.get('name'):
                name = child['name']
            else:
                name = "UNKNOWN"
            children[name] = child
        retval['children'] = children

    def details(self):
        retval = {}
        rawoutput = self.subprocess_check_output(["lsblk", '--json', '-O', '-p'])
        parent = json.loads(rawoutput)
        for child in parent.get('blockdevices',[]):
            #print child['id'] + child['class']
            path = child.get('name')
            retval[path] = child
        for disk, details in retval.items():
            self.label_children(details)
        return self.stringify(retval)

if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    l = LsBlk()
    devdata = l.details()
    pp.pprint(devdata)
    disks = l.disks()
    pp.pprint(disks)
