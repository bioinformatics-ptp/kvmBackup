# -*- coding: utf-8 -*-
"""

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

Created on Wed Oct 21 13:56:55 2015

@author: Paolo Cozzi <bunop@libero.it>
"""

from . import helper
from . import flock

__author__ = "Paolo Cozzi"
__version__ = "1.1"
__all__ = ["helper", "flock"]
