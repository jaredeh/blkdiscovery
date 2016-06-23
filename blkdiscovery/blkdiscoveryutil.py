import subprocess

class BlkDiscoveryUtil:

    def decimalsize(self,value):
        prefixes = "KMGTPEZY"
        i = 0
        out = ""
        while ((i <= len(prefixes)) and ((value > 10000) or (value % 1000 == 0))):
            value = int(value / 1000)
            i += 1

        out += str(value)

        if i > len(prefixes):
            raise "value too big"
        if i > 0:
            out += " " + prefixes[i - 1]

        return out + "B"

    def binarysize(self,value):
        prefixes = "KMGTPEZY"
        i = 0
        out = ""
        while ((i <= len(prefixes)) and ((value > 10240) or (value % 1024 == 0))):
            value = value  >> 10
            i += 1

        out += str(value)

        if i > len(prefixes):
            raise "value too big"
        if i > 0:
            out += " " + prefixes[i - 1]

        return out + "iB"

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

    def subprocess_check_output(self,cmdarray):
        try:
            rawoutput = subprocess.check_output(cmdarray, stderr=subprocess.STDOUT)
        except Exception:
            return ""
        if type(rawoutput) == bytes:
            output = rawoutput.decode("utf-8")
        return output
