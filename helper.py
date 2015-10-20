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
    devs = []
    
    for i in range(len(sources)):
        devs += [(targets[i]["dev"], sources[i]["file"])]
    
    #return dev, file path list
    return devs

def getSnapshotXML(domain):
    """Since I need to do a Snapshot with a XML file, I will create an XML to call
    the appropriate libvirt method"""
    
    #call getDisk to get the disks to do snapshot
    disks = getDisks(domain)
    
    #get a snapshot id
    snapshotId = str(uuid.uuid1()).split("-")[0]
    
    #now construct all diskspec
    diskspecs = []
    
    for disk in disks:
        diskspecs += ["--diskspec %s,file=/var/lib/libvirt/images/%s-%s.img" %(disk[0], disk[0], snapshotId)]

    my_cmd = "virsh snapshot-create-as --domain {domain_name} {snapshotId} {diskspecs} --disk-only --atomic --quiesce --print-xml".format(domain_name=domain.name(), snapshotId=snapshotId, diskspecs=" ".join(diskspecs))    
    
    logger.debug("Executing: %s" %(my_cmd))    
    
    #split the executable
    my_cmds = shlex.split(my_cmd)
    
    #Launch command
    create_xml = subprocess.Popen(my_cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=preexec_fn, shell=False)
    
    #read output in xml
    snapshot_xml = create_xml.stdout.read()
    
    #Lancio il comando e aspetto che termini
    status = create_xml.wait()
    
    if status != 0:
        logger.error("Error for %s:%s" %(my_cmds, create_xml.stderr.read()))
        logger.critical("{exe} return {stato} state".format(stato=status, exe=my_cmds[0]))
        raise Exception, "snapshot-create-as didn't work properly"
        
    return snapshot_xml

def callSnapshot(domain):
    """Create a snapshot for domain"""
    
    #i need a xml file for the domain
    pass
    
    
def backup(domain, parameters):
    """Do all the operation needed for backup"""
    pass

    #TODO: call rotation directive

    #TODO: call dumpXML

    #TODO: call snapshot

    #TODO: copy file

    #TODO: block commit

    #TODO: remove snapshot
