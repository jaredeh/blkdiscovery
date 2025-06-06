import subprocess
from typing import Union, Dict, List, Any

class BlkDiscoveryUtil:

    def decimalsize(self, value: int, /) -> str:
        prefixes = "KMGTPEZY"
        i = 0
        out = ""
        while ((i <= len(prefixes)) and ((value > 10000) or (value % 1000 == 0))):
            value = int(value / 1000)
            i += 1

        out += str(value)

        if i > len(prefixes):
            raise ValueError("value too big")
        if i > 0:
            out += " " + prefixes[i - 1]

        return out + "B"

    def binarysize(self, value: int, /) -> str:
        prefixes = "KMGTPEZY"
        i = 0
        out = ""
        while ((i <= len(prefixes)) and ((value > 10240) or (value % 1024 == 0))):
            value = value  >> 10
            i += 1

        out += str(value)

        if i > len(prefixes):
            raise ValueError("value too big")
        if i > 0:
            out += " " + prefixes[i - 1]

        return out + "iB"

    def stringify(self, json: Union[Dict[Any, Any], List[Any], Any]) -> Union[Dict[str, Any], List[str], str]:
        if isinstance(json, dict):
            retval = {}
            for key, value  in json.items():
                retval[str(key)] = self.stringify(value)
            return retval
        if isinstance(json, list):
            retval = []
            for element in json:
                retval.append(self.stringify(element))
            return retval
        return str(json)

    def subprocess_check_output(self, cmdarray: List[str]) -> str:
        try:
            rawoutput = subprocess.check_output(cmdarray, stderr=subprocess.STDOUT)
        except Exception:
            return ""
        if isinstance(rawoutput, bytes):
            output = rawoutput.decode("utf-8")
        return output
