import re
import subprocess
import sys
import os

class LsStorageController:

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

    def get_block_devices(self):
        devicepath = "/sys/block"
        diskdevices = os.listdir(devicepath)
        return diskdevices

    def lspci_data(self):
        try:
            rawoutput = subprocess.check_output(['lspci'], stderr=subprocess.STDOUT)
        except Exception:
            return ""
        if type(rawoutput) == bytes:
            output = rawoutput.decode("utf-8")
        return output

    def diskbypaths(self):
        rawoutput = subprocess.check_output(['ls', '-alh', '/dev/disk/by-path'], stderr=subprocess.STDOUT)
        if type(rawoutput) == bytes:
            output = rawoutput.decode("utf-8")
        return output

    def sysblock(self):
        rawoutput = subprocess.check_output(['ls', '-alh', '/sys/block/'], stderr=subprocess.STDOUT)
        if type(rawoutput) == bytes:
            output = rawoutput.decode("utf-8")
        return output

    def disk_pcideviceid(self,diskdevice):
        for item in self.diskbypaths().splitlines():
            if diskdevice in item:
                parameter = 'pci-0000:'
                regex = re.compile(parameter + '(.*)')
                match = regex.search(item)
                if match:
                    model = match.group(1).split(".")[0]
                    return model

    def platform(self,disk,details):
        for item in self.sysblock().splitlines():
            if disk in item:
                match = re.search('devices\/platform\/([^\/]+)\/',item)
                if match:
                    controller = match.group(1)
                    m2 = re.search('(.*)\.(\d+)',controller)
                    if m2:
                        name = m2.group(1)
                        details['controller'] = name
                        path = m2.group(2)
                        if not details.get('storagepath'):
                            details['storagepath'] = path
                        return


    def get_storage_path(self,disk,details):
        for item in self.diskbypaths().splitlines():
            if disk in item:
                for parameter in ['usb-', 'scsi-', 'sas-', 'ata-']:
                    regex = re.compile('-(' + parameter + '.*)')
                    match = regex.search(item)
                    if match:
                        storagepath = match.group(1).split(" ")[0].strip()
                        details['storagepath'] = storagepath
                        return

    def get_pci_model(self,disk,pcidevices,details):
        deviceid = self.disk_pcideviceid(disk)
        if deviceid == None:
            return None
        regex = re.compile(deviceid + '(.*)')
        match = regex.search(pcidevices)
        if match:
            model = match.group(1).split(":")[1].strip()
            details['controller'] = model
            return

    def process_device(self,disk,pcidevices):
        details = {}
        fullpath = "/dev/" + disk
        self.get_pci_model(disk,pcidevices,details)
        self.get_storage_path(disk,details)
        self.platform(disk,details)

        return fullpath, details

    def details(self):
        devdata = {}
        pcidevices = self.lspci_data()
        blockdevices = self.get_block_devices()
        for device in blockdevices:
            path, details = self.process_device(device,pcidevices)
            if not details == {}:
                devdata[path] = details
        return self.stringify(devdata)


if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    l = LsStorageController()
    devdata = l.details()
    pp.pprint(devdata)
    #print('----diskpath----')
    #pp.pprint(l.get_disk_paths())
