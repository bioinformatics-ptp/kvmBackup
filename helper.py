# -*- coding: utf-8 -*-
"""
Created on Tue Oct 20 12:43:39 2015

@author: Paolo Cozzi <paolo.cozzi@ptp.it>

A module to deal with KVM backup

"""

import os
import uuid
import shlex
import signal
import libvirt
import logging
import subprocess

# To inspect xml
import xml.etree.ElementTree as ET

# Logging istance
logger = logging.getLogger(__name__)

# A global connection instance
conn = libvirt.open("qemu:///system")

# una funzione che ho trovato qui: https://blog.nelhage.com/2010/02/a-very-subtle-bug/
# e che dovrebbe gestire i segnali strani quando esco da un suprocess
preexec_fn=lambda: signal.signal(signal.SIGPIPE, signal.SIG_DFL)

def dumpXML(domain, path):
    """DumpXML inside PATH"""
    
    dest_file = "%s.xml" %(domain.name())
    dest_file = os.path.join(path, dest_file)
    
    if os.path.exists(dest_file):
        raise Exception, "File %s exists!!" %(dest_file)
        
    dest_fh = open(dest_file, "w")
    
    #dump different xmls files. First of all, the offline dump
    xml = domain.XMLDesc()
    dest_fh.write(xml)
    dest_fh.close()
    
    logger.info("File %s wrote" %(dest_file))

    #All flags: libvirt.VIR_DOMAIN_XML_INACTIVE, libvirt.VIR_DOMAIN_XML_MIGRATABLE, libvirt.VIR_DOMAIN_XML_SECURE, libvirt.VIR_DOMAIN_XML_UPDATE_CPU
    dest_file = "%s-inactive.xml" %(domain.name())
    dest_file = os.path.join(path, dest_file)
    
    if os.path.exists(dest_file):
        raise Exception, "File %s exists!!" %(dest_file)
        
    dest_fh = open(dest_file, "w")
    
    #dump different xmls files. First of all, the offline dump
    xml = domain.XMLDesc(flags=libvirt.VIR_DOMAIN_XML_INACTIVE)
    dest_fh.write(xml)
    dest_fh.close()
    
    logger.info("File %s wrote" %(dest_file))
    
    #Dump a migrate config file
    dest_file = "%s-migratable.xml" %(domain.name())
    dest_file = os.path.join(path, dest_file)
    
    if os.path.exists(dest_file):
        raise Exception, "File %s exists!!" %(dest_file)
        
    dest_fh = open(dest_file, "w")
    
    #dump different xmls files. First of all, the offline dump
    xml = domain.XMLDesc(flags=libvirt.VIR_DOMAIN_XML_INACTIVE+libvirt.VIR_DOMAIN_XML_MIGRATABLE)
    dest_fh.write(xml)
    dest_fh.close()
    
    logger.info("File %s wrote" %(dest_file))

#Define a function to get all disk for a certain domain
def getDisks(domain):
    """Get al disks from a particoular domain"""
    
    #the fromstring method returns the root node
    root = ET.fromstring(domain.XMLDesc())
    
    #then use XPath to search a line like <disk type='file' device='disk'> under <device> tag
    devices = root.findall("./devices/disk[@device='disk']")
    
    #Now find the child element with source tag
    sources = [device.find("source").attrib for device in devices]
    
    #get also dev target
    targets = [device.find("target").attrib for device in devices]
    
    #iterate amoung sources and targets
    if len(sources) != len(targets):
        raise Exception, "Targets and sources lengths are different %s:%s" %(len(sources), len(targets))
    
    #here all the devices I want to back up
    devs = {}
    
    for i in range(len(sources)):
        devs[targets[i]["dev"]] = sources[i]["file"]
    
    #return dev, file path list
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
        
    def getDisks(self):
        """Call getDisk on my instance"""
        
        #get my domain
        domain = self.getDomain()
        
        #call getDisk to get the disks to do snapshot
        return getDisks(domain)
        
    def dumpXML(self):
        """Call dumpXML on my instance"""
        
        #get my domain
        domain = self.getDomain()
        
        #call getDisk to get the disks to do snapshot
        return dumpXML(domain)

    def getSnapshotXML(self):
        """Since I need to do a Snapshot with a XML file, I will create an XML to call
        the appropriate libvirt method"""
        
        #get my domain
        domain = self.getDomain()
        
        #call getDisk to get the disks to do snapshot
        self.disks = self.getDisks()
        
        #get a snapshot id
        self.snapshotId = str(uuid.uuid1()).split("-")[0]
        
        #now construct all diskspec
        diskspecs = []
        
        for disk in self.disks.iterkeys():
            diskspecs += ["--diskspec %s,file=/var/lib/libvirt/images/snapshot_%s_%s-%s.img" %(disk, self.domain_name, disk, self.snapshotId)]
    
        my_cmd = "virsh snapshot-create-as --domain {domain_name} {snapshotId} {diskspecs} --disk-only --atomic --quiesce --print-xml".format(domain_name=domain.name(), snapshotId=self.snapshotId, diskspecs=" ".join(diskspecs))    
        
        logger.debug("Executing: %s" %(my_cmd))    
        
        #split the executable
        my_cmds = shlex.split(my_cmd)
        
        #Launch command
        create_xml = subprocess.Popen(my_cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=preexec_fn, shell=False)
        
        #read output in xml
        self.snapshot_xml = create_xml.stdout.read()
        
        #Lancio il comando e aspetto che termini
        status = create_xml.wait()
        
        if status != 0:
            logger.error("Error for %s:%s" %(my_cmds, create_xml.stderr.read()))
            logger.critical("{exe} return {stato} state".format(stato=status, exe=my_cmds[0]))
            raise Exception, "snapshot-create-as didn't work properly"
            
        return self.snapshot_xml

    def callSnapshot(self):
        """Create a snapshot for domain"""
        
        #Don't redo a snapshot on the same item
        if self.snapshot is not None:
            logger.error("A snapshot is already defined for this domain")
            logger.warn("Returning the current snapshot")
            return self.snapshot
        
        #i need a xml file for the domain
        if self.snapshot_xml is None:
            self.getSnapshotXML()
            
        #Those are the flags I need for creating SnapShot
        [disk_only, atomic, quiesce] = [libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY, libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC, libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_QUIESCE]
        
        #get a domain
        domain = self.getDomain()
        
        #do a snapshot
        logger.info("Creating snapshot %s for %s" %(self.snapshotId, self.domain_name))
        self.snapshot = domain.snapshotCreateXML(self.snapshot_xml, flags=sum([disk_only, atomic, quiesce]))
        
        #Once i've created a snapshot, I can read disks to have snapshot image name
        self.snapshot_disk = self.getDisks()
        
        return self.snapshot
        
    def doBlockCommit(self):
        """Do a blockcommit for every disks shapshotted"""
        
        #get a domain
        domain = self.getDomain()      
        
        ##Those are the flags I need for blockcommit
        [active] = [libvirt.VIR_DOMAIN_BLOCK_COMMIT_ACTIVE]
        
        #A blockcommit for every disks. Using names like libvirt variables. Base is the original image file
        for disk, base in self.disks.iteritems():
            #Top is the image file I want to commit. In this case, is the snapshot file
            top = self.snapshot_disk[disk]
            
            #virsh  blockcommit DockerNode2 hda --active --verbose --pivot
            domain.blockCommit(disk, base, top, flags=sum([active]))
        
    
def backup(domain, parameters):
    """Do all the operation needed for backup"""
    pass

    #TODO: call rotation directive

    #TODO: call dumpXML

    #TODO: call snapshot

    #TODO: copy file

    #TODO: block commit

    #TODO: remove snapshot
