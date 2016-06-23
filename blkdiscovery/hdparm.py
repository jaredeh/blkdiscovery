import re
#hack for python2 support
try:
    from .blkdiscoveryutil import *
except:
    from blkdiscoveryutil import *

class Hdparm(BlkDiscoveryUtil):

    def details(self,device):
        devdata = {}
        hdparmdata = self.read_hdparm_data(device)
        i=0
        section = "Device"
        for line in hdparmdata:
            i += 1
            #pp.pprint(line)
            m1 = re.match('^\S+',str(line))
            if m1:
                s = line.rstrip().split(':')
                if len(s) > 1:
                    #exception for the first section where it's named for the device
                    if s[0] == device:
                        line = "Path: " + device
                    else:
                        section = s[0]
                        if len(s[1]) > 0:
                            line = s[1].lstrip()
                        else:
                            continue
            line = line.strip()
            #this is my attempt to try out a switch/case replacement with a dict
            #I'm looking up a function that is mapped by a dict to parse specialized
            #sections of the hdparm output as it doesn't follow consistent rules
            switch_parse_line = {
                "Device": self.parse_line_device,
                "Configuration": self.parse_line_configuration,
                "Commands/features": self.parse_line_features,
                "Security": self.parse_line_security,
                "Logical Unit WWN Device Identifier": self.parse_line_indentifier,
            }
            case = switch_parse_line.get(section,self.parse_line_default)
            case(line,devdata,section)
        self.scrub(devdata)
        return self.stringify(devdata)

    def read_hdparm_data(self,device):
        try:
            rawdata = self.subprocess_check_output(['hdparm', '-I', device])
            return rawdata.splitlines()
        except:
            return [""]

    def single_space(self,string):
        return " ".join(string.lstrip().rstrip().split())

    def parse_line_device(self,line,devdata,section):
        if not devdata.get(section):
            devdata[section] = {}
        s = line.split(':')
        if len(s) < 2:
            line = "long type:" + s[0]
        self.parse_line_default(line,devdata,section)

    def parse_line_standards(self,ine,devdata,section):
        if not devdata.get(section):
            devdata[section] = {}
        line = line.lstrip()
        s = line.rstrip().split(':')
        if len(s) < 2:
            devdata[section][s] = ""
            return
        devdata[section][s[0]] = s[1]

    def parse_line_configuration(self,line,devdata,section):
        if re.match('^Logical\s+max\s+current$',line):
            return
        if re.match('^\-\-$',line):
            return
        self.parse_line_default(line,devdata,section)

    def parse_line_features(self,line,devdata,section):
        if re.match('^Enabled\s+Supported\:$',line):
            return
        enabled = ': disabled'
        s = line.split('*')
        if len(s) > 1:
            enabled = ': enabled'
            line = s[1]
        line += enabled
        self.parse_line_default(line,devdata,"Features")

    def parse_line_security(self,line,devdata,section):
        if not devdata.get(section):
            devdata[section] = {}
        if re.search('SECURITY ERASE UNIT',line) and re.search('ENHANCED SECURITY ERASE UNIT',line):
            s = line.split('.')
            for subline in s:
                s2 = subline.split('for')
                if len(s2) > 1:
                    key = self.single_space(s2[1] + " (seconds)")
                    val = str(int(s2[0].strip().split('min')[0])*60)
                    devdata[section][key] = val
            return
        devdata[section][self.single_space(line)] = ""

    def parse_line_indentifier(self,line,devdata,section):
        s = line.split(':')
        if len(s) < 2:
            line = section + ":" + s[0]
        section = "Device"
        self.parse_line_default(line,devdata,section)

    def parse_line_default(self,line,devdata,section):
        if not devdata.get(section):
            devdata[section] = {}
        s = line.split(':')
        if len(s) > 1:
            devdata[section][self.single_space(s[0])] = self.single_space(s[1])
            return
        s = line.split('=')
        if len(s) > 1:
            devdata[section][self.single_space(s[0])] = self.single_space(s[1])
            return
        devdata[section][self.single_space(line)] = ""

    def guess_vendor(self,product):
        lookup = {
            "^ST.+": "Seagate",
            "^D...-.+": "IBM",
            "^IBM.+": "IBM",
            "^HITACHI.+": "Hitachi",
            "^IC.+": "Hitachi",
            "^HTS.+": "Hitachi",
            "^FUJITSU.+": "Fujitsu",
            "^MP.+": "Fujitsu",
            "^TOSHIBA.+": "Toshiba",
            "^MK.+": "Toshiba",
            "^MAXTOR.+": "Maxtor",
            "^Pioneer.+": "Pioneer",
            "^PHILIPS.+": "Philips",
            "^QUANTUM.+": "Quantum",
            "FIREBALL.+": "Quantum",
            "^WDC.+": "Western Digital",
            "WD.+": "Western Digital",
            "^MICRON.+": "Micron",
            "^CRUCIAL.+": "Crucial",
            "^SAMSUNG.+": "Samsung",
            "^INTEL.+": "Intel"}
        for pattern, vendor_name in lookup.items():
                if re.match(pattern,product.upper()):
                    return vendor_name
        return None

    def scrub(self,devdata):
        for key, section in devdata.items():
            if key == "Device":
                if section.get('Model Number'):
                    vendor_name = self.guess_vendor(section['Model Number'])
                    if vendor_name:
                        section['Vendor'] = vendor_name
                continue
            if key == "Configuration":
                if not section.get('LBA48 user addressable sectors'):
                    continue
                if not section.get('Logical Sector size'):
                    continue
                sectors = int(section['LBA48 user addressable sectors'].strip())
                sectorsize = int(section['Logical Sector size'].split('bytes')[0].strip())
                size = sectors * sectorsize
                section['Disk Size'] = {'sectors': sectors,
                                        'bytes': size,
                                        'human base2': self.binarysize(size),
                                        'human base10': self.decimalsize(size)}
                continue

if __name__ == '__main__':
    import pprint
    import sys
    pp = pprint.PrettyPrinter(indent=4)
    hp = Hdparm()
    devdata = hp.details(sys.argv[1])
    pp.pprint(devdata)
