import os
import re
from .blkdiscoveryutil import *


class Nvme(BlkDiscoveryUtil):
    """Discover NVMe and NVMe-over-Fabrics namespaces via sysfs.

    Populates fields that hdparm/lsstoragecntlr cannot supply for NVMe-oF
    devices (subsystem NQN, transport, traddr/trsvcid, host NQN, state,
    IO policy, WWN, size, etc.).
    """

    NS_RE = re.compile(r'^nvme\d+n\d+$')

    def _resolve_controller(self, ns):
        """Map a namespace name (e.g. 'nvme0n1') to its controller name (e.g. 'nvme0').

        For local PCIe NVMe, /sys/block/<ns>/device points at the controller.
        For multipath NVMe-oF, it points at the *subsystem*, which contains
        one or more controllers as siblings. Prefer a 'live' one, otherwise
        the first.
        """
        target = self.runner.realpath(f'/sys/block/{ns}/device')
        if not target:
            return None
        base = os.path.basename(target)
        if re.match(r'^nvme\d+$', base):
            return base
        # subsystem dir: scan for controller siblings
        entries = self.runner.listdir(target)
        controllers = sorted(e for e in entries if re.match(r'^nvme\d+$', e))
        if not controllers:
            return None
        for c in controllers:
            state = self.runner.read_file(f'/sys/class/nvme/{c}/state')
            if state == 'live':
                return c
        return controllers[0]

    def _resolve_subsys_dir(self, ns):
        """Resolve the nvme-subsystem sysfs dir for a namespace, if any."""
        target = self.runner.realpath(f'/sys/block/{ns}')
        if not target:
            return None
        # e.g. /sys/devices/virtual/nvme-subsystem/nvme-subsys0/nvme0n1
        m = re.match(r'(.*/nvme-subsys\d+)/', target + '/')
        if m:
            return m.group(1)
        return None

    def _parse_address(self, addr):
        """Parse 'traddr=10.0.1.2,trsvcid=4420' style strings into a dict."""
        out = {}
        if not addr:
            return out
        for piece in addr.split(','):
            if '=' in piece:
                k, v = piece.split('=', 1)
                k = k.strip()
                v = v.strip()
                if v:
                    out[k] = v
        return out

    def _size_bytes(self, ns):
        sectors = self.runner.read_file(f'/sys/block/{ns}/size')
        if sectors is None:
            return None
        try:
            return int(sectors) * 512
        except ValueError:
            return None

    _ZERO_WWNS = {
        '00000000000000000000000000000000',
        '00000000-0000-0000-0000-000000000000',
        'uuid.00000000-0000-0000-0000-000000000000',
        'eui.0000000000000000',
        'nguid.00000000000000000000000000000000',
    }

    def _wwn(self, ns):
        for fname in ('wwid', 'nguid', 'uuid'):
            v = self.runner.read_file(f'/sys/block/{ns}/{fname}')
            if v and v.lower() not in self._ZERO_WWNS:
                return v
        return None

    def process_namespace(self, ns):
        details = {}

        size = self._size_bytes(ns)
        if size:
            details['bytes'] = size
            details['size'] = self.decimalsize(size)

        wwn = self._wwn(ns)
        if wwn:
            details['WWN'] = wwn

        controller = self._resolve_controller(ns)
        if not controller:
            return details

        ctrl_dir = f'/sys/class/nvme/{controller}'
        transport = self.runner.read_file(f'{ctrl_dir}/transport') or 'pcie'
        addr = self.runner.read_file(f'{ctrl_dir}/address')
        subsysnqn = self.runner.read_file(f'{ctrl_dir}/subsysnqn')
        model = self.runner.read_file(f'{ctrl_dir}/model')
        serial = self.runner.read_file(f'{ctrl_dir}/serial')
        firmware = self.runner.read_file(f'{ctrl_dir}/firmware_rev')

        if model:
            details['model'] = model
        if serial:
            details['serial'] = serial
        if firmware:
            details['firmware'] = firmware

        parts = self._parse_address(addr)

        if transport == 'pcie':
            details['disk class'] = 'NVMe'
            if subsysnqn:
                details['storage controller'] = subsysnqn
            pci_addr = parts.get('pcie') or addr
            if pci_addr:
                details['storage path'] = f'pcie:{pci_addr}'
        else:
            details['disk class'] = f'NVMe-oF ({transport})'
            if subsysnqn:
                details['storage controller'] = subsysnqn
            traddr = parts.get('traddr')
            trsvcid = parts.get('trsvcid')
            if traddr and trsvcid:
                details['storage path'] = f'nvme-{transport}:{traddr}:{trsvcid}'
            elif traddr:
                details['storage path'] = f'nvme-{transport}:{traddr}'

            fabric = {'transport': transport}
            if subsysnqn:
                fabric['NQN'] = subsysnqn
            hostnqn = self.runner.read_file(f'{ctrl_dir}/hostnqn')
            if hostnqn:
                fabric['host NQN'] = hostnqn
            hostid = self.runner.read_file(f'{ctrl_dir}/hostid')
            if hostid:
                fabric['host ID'] = hostid
            state = self.runner.read_file(f'{ctrl_dir}/state')
            if state:
                fabric['connection state'] = state
            for k in ('traddr', 'trsvcid', 'host_traddr', 'src_addr'):
                if k in parts:
                    fabric[k] = parts[k]
            subsys_dir = self._resolve_subsys_dir(ns)
            if subsys_dir:
                iopolicy = self.runner.read_file(f'{subsys_dir}/iopolicy')
                if iopolicy:
                    fabric['IO policy'] = iopolicy
            details['fabric'] = fabric

        return details

    def details(self):
        retval = {}
        sysblock = '/sys/block'
        if not self.runner.isdir(sysblock):
            return {}
        for name in sorted(self.runner.listdir(sysblock)):
            if not self.NS_RE.match(name):
                continue
            path = f'/dev/{name}'
            d = self.process_namespace(name)
            if d:
                retval[path] = d
        return self.stringify(retval)


if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    n = Nvme()
    pp.pprint(n.details())
