# -*- coding: utf-8 -*-
"""

kvmBackup - a software for snapshotting KVM images and backing them up
Copyright (C) 2015-2016  PTP

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

Created on Tue Oct 20 12:43:39 2015

@author: Paolo Cozzi <paolo.cozzi@ptp.it>

A module to deal with KVM backup

"""

from __future__ import print_function

import json
import logging
import multiprocessing
import os
import shlex
import shutil
import signal
import subprocess
import uuid

# To inspect xml
import xml.etree.ElementTree as ET

import libvirt
import libvirt_qemu

# Logging istance
logger = logging.getLogger(__name__)

# A global connection instance
conn = libvirt.open("qemu:///system")

# a function found here:
# https://blog.nelhage.com/2010/02/a-very-subtle-bug/
# which attempt to deal with signals when exiting subprocess


def preexec_fn(): return signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def dumpXML(domain, path):
    """DumpXML inside PATH"""

    logger.info("Dumping XMLs for domain %s" % (domain.name()))

    # I need to return wrote files
    xml_files = []

    dest_file = "%s.xml" % (domain.name())
    dest_file = os.path.join(path, dest_file)

    if os.path.exists(dest_file):
        raise Exception("File %s exists!!" % (dest_file))

    dest_fh = open(dest_file, "w")

    # dump different xmls files. First of all, the offline dump
    xml = domain.XMLDesc()
    dest_fh.write(xml)
    dest_fh.close()

    xml_files += [dest_file]
    logger.debug("File %s wrote" % (dest_file))

    # All flags: libvirt.VIR_DOMAIN_XML_INACTIVE,
    # libvirt.VIR_DOMAIN_XML_MIGRATABLE, libvirt.VIR_DOMAIN_XML_SECURE,
    # libvirt.VIR_DOMAIN_XML_UPDATE_CPU
    dest_file = "%s-inactive.xml" % (domain.name())
    dest_file = os.path.join(path, dest_file)

    if os.path.exists(dest_file):
        raise Exception("File %s exists!!" % (dest_file))

    dest_fh = open(dest_file, "w")

    # dump different xmls files. First of all, the offline dump
    xml = domain.XMLDesc(flags=libvirt.VIR_DOMAIN_XML_INACTIVE)
    dest_fh.write(xml)
    dest_fh.close()

    xml_files += [dest_file]
    logger.debug("File %s wrote" % (dest_file))

    # Dump a migrate config file
    dest_file = "%s-migratable.xml" % (domain.name())
    dest_file = os.path.join(path, dest_file)

    if os.path.exists(dest_file):
        raise Exception("File %s exists!!" % (dest_file))

    dest_fh = open(dest_file, "w")

    # dump different xmls files. First of all, the offline dump
    xml = domain.XMLDesc(
        flags=libvirt.VIR_DOMAIN_XML_INACTIVE +
        libvirt.VIR_DOMAIN_XML_MIGRATABLE)
    dest_fh.write(xml)
    dest_fh.close()

    xml_files += [dest_file]
    logger.debug("File %s wrote" % (dest_file))

    return xml_files

# Define a function to get all disk for a certain domain


def getDisks(domain):
    """Get al disks from a particoular domain"""

    # the fromstring method returns the root node
    root = ET.fromstring(domain.XMLDesc())

    # then use XPath to search a line like
    # <disk type='file' device='disk'> under <device> tag
    devices = root.findall("./devices/disk[@device='disk']")

    # Now find the child element with source tag
    sources = [device.find("source").attrib for device in devices]

    # get also dev target
    targets = [device.find("target").attrib for device in devices]

    # iterate amoung sources and targets
    if len(sources) != len(targets):
        raise Exception(
            "Targets and sources lengths are different %s:%s" % (
                len(sources), len(targets)
            )
        )

    # here all the devices I want to back up
    devs = {}

    for i in range(len(sources)):
        devs[targets[i]["dev"]] = sources[i]["file"]

    # return dev, file path list
    return devs


class Snapshot():
    """A class to deal with libvirt snapshot"""

    global conn

    def __init__(self, domain_name):
        """Instantiate a SnapShot instance from a domain name"""

        self.domain_name = domain_name
        self.snapshot_xml = None
        self.disks = None
        self.snapshot_disk = None
        self.snapshotId = None
        self.conn = conn
        self.snapshot = None

    def getDomain(self):
        """Return the libvirt domain by domain_name attribute class"""

        return self.conn.lookupByName(self.domain_name)

    @property
    def domain(self):
        return self.getDomain()

    def domainIsActive(self):
        """Return true if domain is active (VM up and running)"""

        if self.domain.isActive():
            return True

        return False

    def domainHasGuestAgent(self):
        """Test if Guest Agent is up and running"""

        try:
            response = libvirt_qemu.qemuAgentCommand(
                self.domain,
                '{"execute":"guest-ping"}',
                timeout=30,
                flags=0)

        except libvirt.libvirtError as error:
            logger.error(error)
            return False

        data = json.loads(response)

        if 'return' in data:
            return True

        return False

    def getDisks(self):
        """Call getDisk on my instance"""

        # call getDisk to get the disks to do snapshot
        return getDisks(self.domain)

    def dumpXML(self, path):
        """Call dumpXML on my instance"""

        # call getDisk to get the disks to do snapshot
        return dumpXML(self.domain, path)

    def hasCurrentSnapshot(self):
        """call hasCurrentSnapshot on domain class attribute"""

        if self.domain.hasCurrentSnapshot() == 0:
            return False

        else:
            return True

    def getSnapshotXML(self):
        """Since I need to do a Snapshot with a XML file, I will create an XML
        to call the appropriate libvirt method"""

        # call getDisk to get the disks to do snapshot
        self.disks = self.getDisks()

        # get a snapshot id
        self.snapshotId = str(uuid.uuid1()).split("-")[0]

        # now construct all diskspec
        diskspecs = []

        for disk in iter(self.disks):
            diskspecs += [
                "--diskspec %s,file=/var/lib/libvirt/images/snapshot"
                "_%s_%s-%s.img" % (
                    disk, self.domain_name, disk, self.snapshotId)]

        my_cmd = (
            "virsh snapshot-create-as --domain {domain_name} {snapshotId} "
            "{diskspecs} --disk-only --atomic --quiesce --print-xml").format(
                domain_name=self.domain.name(),
                snapshotId=self.snapshotId,
                diskspecs=" ".join(diskspecs))

        logger.debug("Executing: %s" % (my_cmd))

        # split the executable
        my_cmds = shlex.split(my_cmd)

        # Launch command
        create_xml = subprocess.Popen(
            my_cmds, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=preexec_fn,
            shell=False)

        # read output in xml
        self.snapshot_xml = create_xml.stdout.read().decode("ascii")

        # Lancio il comando e aspetto che termini
        status = create_xml.wait()

        if status != 0:
            logger.error("Error for %s:%s" %
                         (my_cmds, create_xml.stderr.read()))
            logger.critical("{exe} returned {stato} state".format(
                stato=status, exe=my_cmds[0]))
            raise Exception("snapshot-create-as didn't work properly")

        return self.snapshot_xml

    def callSnapshot(self):
        """Create a snapshot for domain"""

        # Don't redo a snapshot on the same item
        if self.snapshot is not None:
            logger.error("A snapshot is already defined for this domain")
            logger.warn("Returning the current snapshot")
            return self.snapshot

        # i need a xml file for the domain
        if self.snapshot_xml is None:
            self.getSnapshotXML()

        # Those are the flags I need for creating SnapShot
        [disk_only, atomic, quiesce] = [
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY,
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC,
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_QUIESCE]

        # do a snapshot
        logger.info("Creating snapshot %s for %s" %
                    (self.snapshotId, self.domain_name))
        self.snapshot = self.domain.snapshotCreateXML(
            self.snapshot_xml, flags=sum([disk_only, atomic, quiesce]))

        # Once i've created a snapshot, I can read disks to have snapshot
        # image name
        self.snapshot_disk = self.getDisks()

        # debug
        for disk, top in iter(self.snapshot_disk.items()):
            logger.debug(
                "Created top image {top} for {domain_name} {disk}".format(
                    top=top, domain_name=self.domain.name(), disk=disk))

        return self.snapshot

    def doBlockCommit(self):
        """Do a blockcommit for every disks shapshotted"""

        logger.info("Blockcommitting %s" % (self.domain.name()))

        # A blockcommit for every disks. Using names like libvirt variables.
        # Base is the original image file
        for disk in iter(self.disks):
            # the command to execute
            my_cmd = (
                "virsh blockcommit {domain_name} {disk} --active "
                "--verbose --pivot").format(
                    domain_name=self.domain.name(), disk=disk)
            logger.debug("Executing: %s" % (my_cmd))

            # split the executable
            my_cmds = shlex.split(my_cmd)

            # Launch command
            blockcommit = subprocess.Popen(
                my_cmds,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=preexec_fn,
                shell=False)

            # read output throug processing
            for line in blockcommit.stdout:
                line = line.strip()
                if len(line) == 0:
                    continue

                logger.debug("%s" % (line))

            # Lancio il comando e aspetto che termini
            status = blockcommit.wait()

            if status != 0:
                logger.error("Error for %s:%s" %
                             (my_cmds, blockcommit.stderr.read()))
                logger.critical("{exe} returned {stato} state".format(
                    stato=status, exe=my_cmds[0]))
                raise Exception("blockcommit didn't work properly")

        # After blockcommit, I need to check that image were successfully
        # pivoted
        test_disks = self.getDisks()

        for disk, base in iter(self.disks.items()):
            test_base = test_disks[disk]
            top = self.snapshot_disk[disk]

            if base == test_base and top != test_base:
                # I can remove the snapshotted image
                logger.debug("Removing %s" % (top))
                os.remove(top)

            else:
                logger.error("original base: %s, top: %s, new_base: %s" %
                             (base, top, test_base))
                raise Exception(
                    "Something goes wrong for snaphost %s" % (self.snapshotId))

        # If I arrive here, I can delete snapshot
        self.__snapshotDelete()

    def __snapshotDelete(self):
        """delete current snapshot"""

        [metadata] = [libvirt.VIR_DOMAIN_SNAPSHOT_DELETE_METADATA_ONLY]

        logger.info("Removing snapshot %s" % (self.snapshotId))
        self.snapshot.delete(flags=sum([metadata]))

# from https://bitbucket.org/russellballestrini/virt-back


def rotate(target, retention=3):
    """file rotation routine"""

    for i in range(retention-2, 0, -1):  # count backwards
        old_name = "%s.%s" % (target, i)
        new_name = "%s.%s" % (target, i + 1)

        if os.path.exists(old_name):
            logger.debug("Moving %s into %s" % (old_name, new_name))
            shutil.move(old_name, new_name)

    # Moving the first file
    if os.path.exists(target):
        logger.debug("Moving %s into %s.1" % (target, target))
        shutil.move(target, target + '.1')


def packArchive(target, cpu_limit=8):
    """Launch pigz for compressing files"""

    cpus = multiprocessing.cpu_count()

    # setting number of cpus
    if cpus > cpu_limit:
        cpus = cpu_limit

    my_cmd = "pigz --best --processes %s %s" % (cpus, target)
    logger.debug("Executing: %s" % (my_cmd))

    # split the executable
    my_cmds = shlex.split(my_cmd)

    # Launch command
    pigz = subprocess.Popen(
        my_cmds,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=preexec_fn,
        shell=False)

    # read output throug processing
    for line in pigz.stdout:
        line = line.strip()
        if len(line) == 0:
            continue

        logger.debug("%s" % (line))

    # Lancio il comando e aspetto che termini
    status = pigz.wait()

    if status != 0:
        logger.error("Error for %s:%s" % (my_cmds, pigz.stderr.read()))
        logger.critical("{exe} returned {stato} state".format(
            stato=status, exe=my_cmds[0]))
        raise Exception("pigz didn't work properly")
