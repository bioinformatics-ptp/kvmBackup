#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Oct  9 11:20:46 2015

@author: Paolo Cozzi <paolo.cozzi@ptp.it>
"""

import sys
import yaml
import pprint
import libvirt
import logging
import argparse

# Logging istance
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(sys.argv[0])

# A function to open a config file
def loadConf(file_conf):
    config = yaml.load(open(file_conf))
    
    #try to parse useful data
    return config
    

# A global connection instance
conn = libvirt.open("qemu:///system")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Backup of KVM domains')
    parser.add_argument("-c", "--config", required=True, type=str, help="The config file")
    args = parser.parse_args()
    

    domains = [domain.name() for domain in conn.listAllDomains()]
    
    pprint.pprint(domains)
    
    config = loadConf(args.config)
    
    pprint.pprint(config)

