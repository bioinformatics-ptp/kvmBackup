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

Created on Wed Oct 21 13:08:56 2015

@author: Paolo Cozzi <paolo.cozzi@ptp.it>

Simple lockfile to detect previous instances of app (Python recipe
http://code.activestate.com/recipes/498171/)

"""

from __future__ import print_function

import logging
import os
import socket

# Logging istance
logger = logging.getLogger(__name__)


class flock(object):
    '''Class to handle creating and removing (pid) lockfiles'''

    # custom exceptions
    class FileLockAcquisitionError(Exception):
        pass

    class FileLockReleaseError(Exception):
        pass

    # convenience callables for formatting
    def addr(self): return '%d@%s' % (self.pid, self.host)
    def fddr(self): return '<%s %s>' % (self.path, self.addr())

    def pddr(self, lock): return '<%s %s@%s>' %\
        (self.path, lock['pid'], lock['host'])

    def __init__(self, path, debug=None):
        self.pid = os.getpid()
        self.host = socket.gethostname()
        self.path = path
        self.debug = debug  # set this to get status messages

    def acquire(self):
        '''Acquire a lock, returning self if successful, False otherwise'''
        if self.islocked():
            if self.debug:
                lock = self._readlock()
                logger.error('Previous lock detected: %s' % self.pddr(lock))
            return False
        try:
            fh = open(self.path, 'w')
            fh.write(self.addr())
            fh.close()
            if self.debug:
                logger.debug('Acquired lock: %s' % self.fddr())
        except:
            if os.path.isfile(self.path):
                try:
                    os.unlink(self.path)
                except:
                    pass
            raise (self.FileLockAcquisitionError,
                   'Error acquiring lock: %s' % self.fddr())
        return self

    def release(self):
        '''Release lock, returning self'''
        if self.ownlock():
            try:
                os.unlink(self.path)
                if self.debug:
                    logger.debug('Released lock: %s' % self.fddr())
            except:
                raise (self.FileLockReleaseError,
                       'Error releasing lock: %s' % self.fddr())
        return self

    def _readlock(self):
        '''Internal method to read lock info'''
        try:
            lock = {}
            fh = open(self.path)
            data = fh.read().rstrip().split('@')
            fh.close()
            lock['pid'], lock['host'] = data
            return lock
        except:
            return {'pid': 8**10, 'host': ''}

    def islocked(self):
        '''Check if we already have a lock'''
        try:
            lock = self._readlock()
            os.kill(int(lock['pid']), 0)
            return (lock['host'] == self.host)
        except:
            return False

    def ownlock(self):
        '''Check if we own the lock'''
        lock = self._readlock()
        return (self.fddr() == self.pddr(lock))

    def __del__(self):
        '''Magic method to clean up lock when program exits'''
        self.release()

# ========

# Test programs: run test1.py then test2.py (in the same dir)
# from another teminal -- test2.py should print
# a message that there is a lock in place and exit.


if __name__ == "__main__":
    # test1.py
    from time import sleep

    # from flock import flock
    lock = flock('tmp.lock', True).acquire()
    if lock:
        sleep(30)
    else:
        print('locked!')

    # test2.py
    from flock import flock
    lock = flock('tmp.lock', True).acquire()
    if lock:
        print('doing stuff')
    else:
        print('locked!')
