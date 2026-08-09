import os
import shlex
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Union


class LocalRunner:
    """Run commands and read sysfs on this machine."""

    def run(self, cmdarray: List[str]) -> str:
        try:
            rawoutput = subprocess.check_output(cmdarray, stderr=subprocess.STDOUT)
        except Exception:
            return ""
        return rawoutput.decode("utf-8", errors="replace")

    def read_file(self, path: str) -> Optional[str]:
        try:
            with open(path) as f:
                return f.read().strip()
        except OSError:
            return None

    def listdir(self, path: str) -> List[str]:
        try:
            return os.listdir(path)
        except OSError:
            return []

    def realpath(self, path: str) -> Optional[str]:
        try:
            return os.path.realpath(path)
        except OSError:
            return None

    def isdir(self, path: str) -> bool:
        return os.path.isdir(path)


class SshRunner:
    """Run the same commands and sysfs reads on a remote machine over ssh.

    Everything is prefixed with `sudo -n`: hdparm, blkid and parts of sysfs
    need root, and passwordless sudo on the remote is assumed. A failing
    command yields "" here exactly like it does locally, so an unreachable
    host or a missing tool degrades to empty results rather than an exception.
    """

    def __init__(self, host: str, sudo: bool = True, ssh_options: Optional[List[str]] = None) -> None:
        self.host = host
        self.sudo = sudo
        # ponytail: every sysfs read is its own ssh round trip. Connection
        # multiplexing makes that ~1ms instead of ~100ms, which is cheaper than
        # writing a batching protocol. Ship a single remote script if a host
        # with hundreds of namespaces ever gets slow.
        control_path = os.path.join(tempfile.gettempdir(), f"blkdiscovery-{os.getpid()}-%C")
        self.ssh_options = ssh_options if ssh_options is not None else [
            '-o', 'BatchMode=yes',
            '-o', 'ControlMaster=auto',
            '-o', f'ControlPath={control_path}',
            '-o', 'ControlPersist=60s',
        ]

    def ssh_command(self, cmdarray: List[str]) -> List[str]:
        remote = ' '.join(shlex.quote(arg) for arg in cmdarray)
        if self.sudo:
            remote = f"sudo -n {remote}"
        return ['ssh', *self.ssh_options, self.host, remote]

    def run(self, cmdarray: List[str]) -> str:
        try:
            #stderr is dropped rather than merged: ssh's own chatter would end
            #up in the output the parsers see
            rawoutput = subprocess.check_output(self.ssh_command(cmdarray),
                                                stderr=subprocess.DEVNULL)
        except Exception:
            return ""
        return rawoutput.decode("utf-8", errors="replace")

    def read_file(self, path: str) -> Optional[str]:
        return self.run(['cat', path]).strip() or None

    def listdir(self, path: str) -> List[str]:
        return [line for line in self.run(['ls', '-1', path]).splitlines() if line]

    def realpath(self, path: str) -> Optional[str]:
        return self.run(['readlink', '-f', path]).strip() or None

    def isdir(self, path: str) -> bool:
        return bool(self.run(['sh', '-c', f"test -d {shlex.quote(path)} && echo 1"]).strip())


class BlkDiscoveryUtil:

    def __init__(self, runner: Optional[Any] = None) -> None:
        self.runner = runner or LocalRunner()

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
