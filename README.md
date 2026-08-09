# blkdiscovery

Finds block devices and extracts lots of details from Linux, as JSON.

```
sudo blkdiscovery                  # this machine
blkdiscovery --host user@server    # a remote machine, over ssh
```

Discovery shells out to `lsblk`, `blkid`, `hdparm`, `lspci` and `nvme` sysfs,
all of which want root. Locally that means running under `sudo`; remotely
every command is prefixed with `sudo -n`, so the ssh user needs passwordless
sudo on the target. Connections are multiplexed, so a run is one ssh login.

Every command and file read goes through a runner object, so anything else
that can run a command and read a file works too:

```python
from blkdiscovery import BlkDiscovery
from blkdiscovery.blkdiscoveryutil import SshRunner

BlkDiscovery(host='user@server').details()
BlkDiscovery(runner=SshRunner('server', sudo=False)).details()
```
