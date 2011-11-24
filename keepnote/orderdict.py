"""
    KeepNote
    OrderDict module
"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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






class OrderDict (dict):
    """
    An ordered dict
    """

    def __init__(self, *args, **kargs):

        if len(args) > 0 and hasattr(args[0], "next"):
            dict.__init__(self)
            self._order = []
            for k, v in args[0]:
                self._order.append(k)
                dict.__setitem__(self, k, v)
        else:
            dict.__init__(self, *args, **kargs)
            self._order = dict.keys(self)
    
    # The following methods keep names in sync with dictionary keys
    def __setitem__(self, key, value):
        if key not in self:
            self._order.append(key)
        dict.__setitem__(self, key, value)
    
    def __delitem__(self, key):
        self._order.remove(key)
        dict.__delitem__(self, key)

    def update(self, dct):
        for key in dct:
            if key not in self:
                self._order.append(key)
        dict.update(self, dct)
    
    def setdefault(self, key, value):
        if key not in self:
            self._order.append(key)
        return dict.setdefault(self, key, value)
    
    def clear(self):
        self._order = []
        dict.clear(self)

    # keys are always sorted in order added
    def keys(self):
        return list(self._order)

    def iterkeys(self):
        return iter(self._order)
    
    def values(self):
        return [self[key] for key in self._order]
    
    def itervalues(self):
        for key in self._order:
            yield self[key]

    def items(self):
        return [(key, self[key]) for key in self._order]
        
    def iteritems(self):
        for key in self._order:
            yield (key, self[key])

    def __iter__(self):
        return iter(self._order)
    
