import sys
import subprocess
import json

class LsBlk:

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
        rawoutput = subprocess.check_output(["lsblk", '--json', '-O', '-p'], stderr=subprocess.STDOUT)
        if type(rawoutput) == bytes:
            rawoutput = rawoutput.decode("utf-8")
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
