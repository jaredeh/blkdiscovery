import json
#hack for python2 support
try:
    from .blkdiscoveryutil import *
except:
    from blkdiscoveryutil import *

class LsHw(BlkDiscoveryUtil):

    def bustype(self,storage):
        capabilities = storage.get('capabilities',{})
        configuration = storage.get('configuration',{})
        if configuration.get('driver','') == 'usb-storage':
            return "USB"
        if configuration.get('driver','') == 'ahci':
            return "AHCI HBA"
        if capabilities.get('emulated','') == 'Emulated device':
            return "AHCI HBA"
        return "SCSI HBA"

    def iterate_disks(self,parent,retval,bus):
        for child in parent.get('children',[]):
            #print child['id'] + child['class']
            if child['class'] == "disk":
                if type(child.get('logicalname')) is list:
                    name = child.get('logicalname')[0]
                else:
                    name = child.get('logicalname')
                retval[name] = child
                retval[name]['controller class'] = bus
            if child['class'] == "storage":
                #pp.pprint(child.keys())
                bus = self.bustype(child)
            self.iterate_disks(child,retval,bus)

    def details(self):
        retval = {}
        rawoutput = self.subprocess_check_output(["lshw", '-json'])
        try:
            parent = json.loads(rawoutput)
        except:
            #if the json fails, look at running as root
            parent = {}
        self.iterate_disks(parent,retval,"")
        return self.stringify(retval)

if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    lshw = LsHw()
    devdata = lshw.details()
    pp.pprint(devdata)
