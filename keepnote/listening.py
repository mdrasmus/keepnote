"""

    KeepNote
    Listener (Observer) pattern

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@alum.mit.edu>
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


class Listeners (object):
    """Maintains a list of listeners (functions) that are called when the 
       notify function is called.
    """

    def __init__(self):
        self._listeners = []
        self._suppress = {}
    
    
    def add(self, listener):
        """Add a listener function to the list"""
        self._listeners.append(listener)
        self._suppress[listener] = 0
    
    
    def remove(self, listener):
        """Remove a listener function from list"""
        self._listeners.remove(listener)
        del self._suppress[listener]
    
    
    def clear(self):
        """Clear listener list"""
        self._listeners = []
        self._suppress = {}
    
    
    def notify(self, *args, **kargs):
        """Notify listeners"""
        for listener in self._listeners:
            if self._suppress[listener] == 0:
                listener(*args, **kargs)


    def suppress(self, listener=None):
        """Suppress notification"""
        if listener is not None:
            self._suppress[listener] += 1
        else:
            for l in self._suppress:
                self._suppress[l] += 1
    
    
    def resume(self, listener=None):
        """Resume notification"""
        if listener is not None:
            self._suppress[listener] -= 1
        else:
            for l in self._suppress:
                self._suppress[l] -= 1
    
