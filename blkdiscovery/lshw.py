import sys
import pprint
import subprocess
import json

class LsHw:

    def stringify(self,json):
        if type(json) == dict:
            retval = {}
            for key, value  in json.items():
                retval[str(key)] = self.stringify(value)
            return retval
        if type(json) == list:
            retval = []
            for element in json:
                retval.append(self.stringify(element))
            return retval
        return str(json)

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
        rawoutput = subprocess.check_output(["lshw", '-json'], stderr=subprocess.STDOUT)
        if type(rawoutput) == bytes:
            rawoutput = rawoutput.decode("utf-8")
        parent = json.loads(rawoutput)
        self.iterate_disks(parent,retval,"")
        return self.stringify(retval)

if __name__ == '__main__':
    pp = pprint.PrettyPrinter(indent=4)
    lshw = LsHw()
    devdata = lshw.details()
    pp.pprint(devdata)
