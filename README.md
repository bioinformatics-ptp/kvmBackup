
kvmBackup
=========================================================================
a software for snapshotting KVM images and backing them up. More information could be
found in our [Wiki](https://github.com/bioinformatics-ptp/kvmBackup/wiki)

## License

kvmBackup - a software for snapshotting KVM images and backing them up  
Copyright (C) 2015-2022  Paolo Cozzi

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

## Requirements

* [KVM](http://www.linux-kvm.org/page/Main_Page) and [libvirt](http://libvirt.org/index.html) packages installed
* [QEMU Guest agent](http://wiki.libvirt.org/page/Qemu_guest_agent) installed on every guest
* Guest images in [qcow2](https://en.wikipedia.org/wiki/Qcow) format
* [pigz](http://zlib.net/pigz/)
* python [yaml](http://pyyaml.org/) and [libvirt](https://libvirt.org/python.html)

## Background

Snapshot is a common industry term denoting the ability to record the state of a
storage device at any given moment and preserve that snapshot as a guide for restoring
the storage device in the event that it fails. A snapshot primarily creates a point-in-time
copy of the data. Typically, snapshot copy is done instantly and made available
for use by other applications such as data protection, data analysis and reporting,
and data replication applications. The original copy of the data continues to be
available to the applications without interruption, while the snapshot copy is
used to perform other functions on the data.

[Snapshots in QEMU][SnapshotsQemu] are images that refer to an original image using
[Redirect-on-Write][redirect] to avoid changing the original image. The main advantage
is that new writes to the original volume are redirected to another location set aside
for snapshot. The original location contains the point-in-time data of the Guest,
that is, snapshot, and the changed data reside on the snapshot storage. While snapshotting,
[QEMU Guest Agent][qemu-agent] ensure you have a consistent disk state. Once snapshot
is completed, a backup could be done by copying the original image in another location.
Once backup is completed, the data from the snapshot storage must be reconciled back
into the original volume, before removing snapshot.

You can have a more detailed picture of snapshot by reading our [wiki - Introduction][wiki-introduction]

kvmBackup tries to automatize such operations, by backing up domain configuration files
and qcow images in a single backup file for each domain. The whole backup process could be
executed by cron, and older backup copies are handled by rotation.

[SnapshotsQemu]: http://wiki.qemu.org/Documentation/CreateSnapshot
[redirect]: http://www.ibm.com/developerworks/tivoli/library/t-snaptsm1/index.html
[qemu-agent]: http://wiki.libvirt.org/page/Qemu_guest_agent
[wiki-introduction]: https://github.com/bioinformatics-ptp/kvmBackup/wiki/Introduction#introduction

## Installation

kvmBackup is a simple Python script which use libvirt python API and qemu commands
to snapshot KVM images and configuration file. You can install software simply using git:

```bash
$ git clone https://github.com/bioinformatics-ptp/kvmBackup.git
```

More information in installing `kvmBackup` could be found in our [wiki - Install kvmBackup][install-kvmBackup]

[install-kvmBackup]: https://github.com/bioinformatics-ptp/kvmBackup/wiki/Using-kvmBackup#install-kvmbackup

## Configuration

kvmBackup read a yaml file in order to know which Guest need backup. For instance:

```yaml
cloud1: #The hostname which will do backup
    domains:
        DockerNode1: # A Guest domain name
            #day_of_week: [Sun, Mon, Tue, Wed, Thu, Fri, Sat]
            day_of_week: [Sun] #when backup will be done (Dat of week)
            rotate: 4 # how many backup will be stored.
    backupdir: /mnt/cloud/kvm_backup/cloud1 # were backup will be placed
```

The first level (`cloud1` in the example) is the name of the host in which those
configurations apply; it could be determined by typing `hostname -s`. Configurations
defined under a different hostname will not by applied in such host. The second yaml
level define a `domain` by specyfing all Guest domains we need to provide a backup,
and a `backupdir` directory in which backup will be placed. In this directory will
be placed a directory for each domain, in which backup will be placed. Then in the
third level you need to specify the domain names to backup (you can inspect domain
names by typing `virsh list --all`), and in its sublevels you need to specify the
day of week where the backup will be done and how many bakcup use for rotation

More information on kvmBackup configuration could be found in our [wiki - Configure kvmBackup][configure-kvmBacup]

[configure-kvmBacup]: https://github.com/bioinformatics-ptp/kvmBackup/wiki/Using-kvmBackup#configure-kvmbackup

## Usage

Launch kvmBackup as a provileged user (`root` or using `sudo`) by specyfing the
path of your config file:

```bash
$ kvmBackup.py --config </path/to/config.yaml>
```

It's better to run kvmBackup every day using cron. Here's an example of `/etc/crontab`
in Centos 7:

```
SHELL=/bin/bash
PATH=/sbin:/bin:/usr/sbin:/usr/bin
MAILTO=root

# For details see man 4 crontabs

# Example of job definition:
# .---------------- minute (0 - 59)
# |  .------------- hour (0 - 23)
# |  |  .---------- day of month (1 - 31)
# |  |  |  .------- month (1 - 12) OR jan,feb,mar,apr ...
# |  |  |  |  .---- day of week (0 - 6) (Sunday=0 or 7) OR sun,mon,tue,wed,thu,fri,sat
# |  |  |  |  |
# *  *  *  *  * user-name  command to be executed
  0  2  *  *  * root /mnt/cloud/Utilities/kvmBackup/kvmBackup.py --config /mnt/cloud/Utilities/kvmBackup/config.yml >> /var/log/kvmBackup 2>&1
```

More information in using kvmBackup could be found in our [wiki - Running kvmBackup][running-kvmBackup]

[running-kvmBackup]: https://github.com/bioinformatics-ptp/kvmBackup/wiki/Using-kvmBackup#running-kvmbackup

## Restoring a backup

Pleas see our [wiki - Restoring a backup][restoring-backup]

[restoring-backup]: https://github.com/bioinformatics-ptp/kvmBackup/wiki/Restoring-a-backup#restoring-a-backup
