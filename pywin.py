"""

    Helper functions for windows

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@mit.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#

import os


def get_local_drives():
    # hack that doesn't require win32api
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        if os.path.exists(drive + ":\\"):
            yield drive + ":\\"


def find_path(path, drives=None):
    """Find a path that exists on a list of drives"""
	
    if drives is None:
        drives = get_local_drives()
	
    for drive in drives:
        path2 = os.path.join(drive, path)
        if os.path.exists(path2):
            return path2
    
    raise Exception("Path '%s' not found" % path)
