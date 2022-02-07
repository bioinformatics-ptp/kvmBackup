#! /usr/bin/env python
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

Created on Fri Oct  9 11:20:46 2015

@author: Paolo Cozzi <paolo.cozzi@ptp.it>

"""

from __future__ import print_function

import argparse
import datetime
import logging
import os
import shutil
import socket
import sys
import tarfile

import libvirt
import yaml

# my functions
from Lib import flock, helper

# the program name
prog_name = os.path.basename(sys.argv[0])

# Logging istance
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(prog_name)

notice = """
kvmBackup.py  Copyright (C) 2015-2016  PTP
This program comes with ABSOLUTELY NO WARRANTY; for details type
    `kvmBackup.py --help'.
This is free software, and you are welcome to redistribute it
under certain conditions; see LICENSE.txt for details.

"""


def loadConf(file_conf):
    """A function to open a config file"""

    config = yaml.load(open(file_conf))

    # read my defined domains
    hostname = socket.gethostname()
    hostname = hostname.split(".")[0]

    # try to parse useful data
    mydomains = config[hostname]["domains"]

    # get my backup directory
    backupdir = config[hostname]["backupdir"]

    return mydomains, backupdir, config


def checkDay(day):
    """A function to check current day of the week"""

    now = datetime.datetime.now()
    today = now.strftime("%a")

    if today == day:
        return True

    return False


def filterDomains(domains, user_domains):
    """filter domamin by user domains"""

    # Those are user domains (as a list)
    user_domains = [domain.strip() for domain in user_domains.split(",")]
    found_domains = []

    # test for domain existances
    for domain in user_domains:
        if domain not in domains:
            logger.error("User domain '%s' not found" % (domain))

        else:
            found_domains += [domain]

    # Now return the filtered domains
    return found_domains


def backup(domain, parameters, backupdir):
    """Do all the operation needed for backup"""

    # create a snapshot instance
    snapshot = helper.Snapshot(domain)

    # check if domain is active
    if not snapshot.domainIsActive():
        logger.error(
            "domain '%s' is not Active: is VM up and running?" % domain)
        raise NotImplementedError("Cannot backup an inactive domain!")

    # check if no snapshot are defined
    if snapshot.hasCurrentSnapshot() is True:
        raise Exception("Domain '%s' has already a snapshot" % (domain))

    # changing directory
    olddir = os.getcwd()
    workdir = os.path.join(backupdir, domain)

    # creating directory if not exists
    if not os.path.exists(workdir) and not os.path.isdir(workdir):
        logger.info("Creating directory '%s'" % (workdir))
        os.mkdir(workdir)

    # cange directory
    os.chdir(workdir)

    # a timestamp directory in which to put files
    date = datetime.datetime.now().strftime('%Y-%m-%d')
    datadir = os.path.join(workdir, date)

    # creating datadir
    logger.debug("Creating directory '%s'" % (datadir))
    os.mkdir(datadir)

    # define the target backup
    ext, tar_mode = '.tar', 'w'

    tar_name = domain + ext
    tar_path = os.path.join(workdir, tar_name)
    tar_path_gz = tar_path + ".gz"

    # call rotation directive
    if os.path.isfile(tar_path_gz):  # if file exists, run rotate
        logger.info('rotating backup files for ' + domain)
        helper.rotate(tar_path_gz, parameters["rotate"])

    tar = tarfile.open(tar_path, tar_mode)

    # call dumpXML
    xml_files = snapshot.dumpXML(path=datadir)

    # Add xmlsto archive, and remove original file
    logger.info("Adding XMLs files for domain '%s' to archive '%s'" %
                (domain, tar_path))

    for xml_file in xml_files:
        # backup file with its relative path
        xml_file = os.path.basename(xml_file)
        xml_file = os.path.join(date, xml_file)

        tar.add(xml_file)
        logger.debug("'%s' added" % (xml_file))

        logger.debug("removing '%s' from '%s'" % (xml_file, datadir))
        os.remove(xml_file)

    # call snapshot
    snapshot.callSnapshot()

    logger.info("Adding image files for '%s' to archive '%s'" %
                (domain, tar_path))

    # copying file
    for disk, source in iter(snapshot.disks.items()):
        dest = os.path.join(datadir, os.path.basename(source))

        logger.debug("copying '%s' to '%s'" % (source, dest))
        shutil.copy2(source, dest)

        # backup file with its relative path
        img_file = os.path.basename(dest)
        img_file = os.path.join(date, img_file)
        logger.debug("Adding '%s' to archive '%s'" % (img_file, tar_path))
        tar.add(img_file)

        logger.debug("removing '%s' from '%s'" % (img_file, datadir))
        os.remove(img_file)

    # block commit (and delete snapshot)
    snapshot.doBlockCommit()

    # closing archive
    tar.close()

    # Now launcing subprocess with pigz
    logger.info("Compressing '%s'" % (tar_name))
    helper.packArchive(target=tar_name)

    # revoving EMPTY datadir
    logger.debug("removing '%s'" % (datadir))
    os.rmdir(datadir)

    # return to the original directory
    os.chdir(olddir)

    logger.info("Backup for '%s' completed" % (domain))


# A global connection instance
conn = libvirt.open("qemu:///system")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Backup of KVM-qcow2 domains')
    parser.add_argument("-c", "--config", required=True,
                        type=str, help="The config file")
    parser.add_argument("--force", required=False, action='store_true',
                        default=False, help="Force backup (with rotation)")
    parser.add_argument(
        "--domains", required=False, type=str,
        help=("comma separated list of domains to backup ('virsh list "
              "--all' to get domains)"))
    args = parser.parse_args()

    # logging notice
    sys.stderr.write(notice)
    sys.stderr.flush()

    # a flat to test if there were errors
    flag_errors = False

    # Starting software
    logger.info("Starting '%s'" % (prog_name))

    lockfile = os.path.splitext(os.path.basename(sys.argv[0]))[0] + ".lock"
    lockfile_path = os.path.join("/var/run", lockfile)

    lock = flock.flock(lockfile_path, True).acquire()

    if not lock:
        logger.error(
            "Another istance of '%s' is running. Please wait for its "
            "termination or kill the running application" % (sys.argv[0]))
        sys.exit(-1)

    # get all domain names
    domains = [domain.name() for domain in conn.listAllDomains()]

    # filter domains with user provides domains (if needed)
    if args.domains is not None:
        logger.info("Checking '%s' domains" % (args.domains))
        domains = filterDomains(domains, args.domains)

    # parse configuration file
    mydomains, backupdir, config = loadConf(args.config)

    # test for directory existance
    if not os.path.exists(backupdir) and os.path.isdir(backupdir) is False:
        logger.info("Creating directory '%s'" % (backupdir))
        os.mkdir(backupdir)

    # debug
    # pprint.pprint(mydomains)

    for domain_name, parameters in iter(mydomains.items()):
        # check if bakcup is needed
        domain_backup = False

        # check if configuration domain exists or was filtered out
        if domain_name not in domains:
            logger.warn("Ignoring domain '%s'" % (domain_name))
            continue

        for day in parameters["day_of_week"]:
            if checkDay(day) is True or args.force is True:
                logger.info("Ready for backup of '%s'" % (domain_name))
                domain_backup = True

                # do backup stuff
                try:
                    backup(domain_name, parameters, backupdir)

                except Exception as message:
                    logger.exception(message)
                    logger.error("Domain '%s' was not backed up" %
                                 (domain_name))
                    flag_errors = True

                # breaking cicle
                break

        if domain_backup is False:
            logger.debug("Ignoring '%s' domain" % (domain_name))

    # end of the program
    if flag_errors is False:
        logger.info("'%s' completed successfully" % (prog_name))
    else:
        logger.warn("'%s' completed with error(s)" % (prog_name))
