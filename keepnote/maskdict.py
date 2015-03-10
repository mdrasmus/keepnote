"""
    KeepNote

    MaskDict model.  Mask certain keys from an underlying dictionary

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


class MaskDict (dict):
    """
    A dict with some keys masked
    """

    def __init__(self, basedict, mask=[]):
        self._dict = basedict
        self._mask = set(mask)

    def add_mask(self, mask):
        self._mask.add(mask)

    def remove_mask(self, mask):
        self._mask.remove(mask)

    def set_dict(self, basedict):
        self._dict = basedict

    def get_dict(self):
        return self._dict

    # The following methods keep names in sync with dictionary keys
    def __setitem__(self, key, value):
        self._dict.__setitem__(key, value)

    def __getitem__(self, key):
        if key in self._mask:
            raise KeyError(key)
        return self._dict.__getitem__(key)

    def __delitem__(self, key):
        self._dict.__delitem__(key)

    def update(self, dct):
        self._dict.update(dct)

    def get(self, key, default=None):
        if key in self._mask:
            return default
        else:
            return self._dict.get(key, default)

    def setdefault(self, key, value):
        return self._dict.setdefault(key, value)

    def clear(self):
        self._dict.clear()

    def keys(self):
        return [k for k in self._dict if k not in self._mask]

    def iterkeys(self):
        return (k for k in self._dict if k not in self._mask)

    def values(self):
        return [self._dict[key] for key in self._dict if key not in self._mask]

    def itervalues(self):
        return (self._dict[key] for key in self._dict if key not in self._mask)

    def items(self):
        return [(key, self._dict[key]) for key in self._dict
                if key not in self._mask]

    def iteritems(self):
        return ((key, self._dict[key]) for key in self._dict
                if key not in self._mask)

    def __iter__(self):
        return (key for key in self._dict if key not in self._mask)

    def __repr__(self):
        return repr(dict(self.iteritems()))

    def __str__(self):
        return str(dict(self.iteritems()))
