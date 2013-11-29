"""

    KeepNote
    Task object for threading

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

# python imports
from heapq import heappop


NULL = object()


class LRUDict (dict):
    """A Least Recently Used (LRU) dict-based cache"""

    def __init__(self, limit=1000):
        dict.__init__(self)
        self._limit = limit
        self._age = 0
        self._age_lookup = {}
        self._ages = []
        assert limit > 1

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)

        self._age_lookup[key] = self._age
        self._ages.append((self._age, key))
        self._age += 1

        # shirk cache if it is over limit
        while len(self._ages) > self._limit:
            minage, minkey = heappop(self._ages)
            if self._age_lookup[minkey] == minage:
                del self._age_lookup[minkey]
                self.__delitem__(minkey)

    def __getitem__(self, key):
        val = dict.__getitem(self, key)

        self._age_lookup[key] = self._age
        self._ages.append((self._age, key))
        self._age += 1

        return val


class DictCache (object):

    def __init__(self, func, cache_dict):
        self._func = func
        self._cache_dict = cache_dict

    def __getitem__(self, key):
        val = self._cache_dict.get(key, NULL)
        if val is NULL:
            val = self._cache_dict[key] = self._func(key)
        return val


class LRUCache (DictCache):

    def __init__(self, func, limit=1000):
        DictCache.__init__(self, func, LRUDict(limit))
