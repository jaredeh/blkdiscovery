import re
from .blkdiscoveryutil import *

#a PCI address as it appears in a sysfs path, e.g. 0000:81:00.0
PCI_ADDRESS_RE = re.compile(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]')

PCIE_LINK_FILES = {
    'PCIe link speed': 'current_link_speed',
    'PCIe link width': 'current_link_width',
    'PCIe max link speed': 'max_link_speed',
    'PCIe max link width': 'max_link_width',
}


class LsStorageController(BlkDiscoveryUtil):

    def get_block_devices(self):
        devicepath = "/sys/block"
        diskdevices = self.runner.listdir(devicepath)
        return diskdevices

    def lspci_data(self):
        return self.runner.run(['lspci'])

    def diskbypaths(self):
        return self.runner.run(['ls', '-alh', '/dev/disk/by-path'])

    def sysblock(self):
        return self.runner.run(['ls', '-alh', '/sys/block/'])

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
                match = re.search('devices/platform/([^/]+)/',item)
                if match:
                    controller = match.group(1)
                    m2 = re.search(r'(.*)\.(\d+)',controller)
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

    def pci_address(self,disk):
        """The innermost PCI address in a disk's sysfs path, i.e. the endpoint it hangs off.

        For NVMe that is the drive itself. For SATA/SAS/USB it is the HBA, whose
        link is shared by every port on it.
        """
        target = self.runner.realpath(f"/sys/block/{disk}")
        if not target:
            return None
        addresses = PCI_ADDRESS_RE.findall(target)
        return addresses[-1] if addresses else None

    def get_pcie_link(self,disk,details):
        address = self.pci_address(disk)
        if not address:
            return
        for key, filename in PCIE_LINK_FILES.items():
            value = self.runner.read_file(f"/sys/bus/pci/devices/{address}/{filename}")
            #non-PCIe parents report "Unknown"
            if value and not value.startswith('Unknown'):
                details[key] = value

    def process_device(self,disk,pcidevices):
        details = {}
        fullpath = f"/dev/{disk}"
        self.get_pci_model(disk,pcidevices,details)
        self.get_storage_path(disk,details)
        self.platform(disk,details)
        self.get_pcie_link(disk,details)

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
