"""

    KeepNote
    utilities

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


class PushIter (object):
    """
    Wrap an iterator in another iterator that allows one to push new
    items onto the front of the iteration stream
    """
    def __init__(self, it):
        self._it = iter(it)
        self._queue = []

    def __iter__(self):
        return self

    def next(self):
        if len(self._queue) > 0:
            return self._queue.pop()
        else:
            return self._it.next()

    def push(self, item):
        """Push a new item onto the front of the iteration stream"""
        self._queue.append(item)


def compose2(f, g):
    """
    Compose two functions into one

    compose2(f, g)(x) <==> f(g(x))
    """
    return lambda *args, **kargs: f(g(*args, **kargs))


def compose(*funcs):
    """Composes two or more functions into one function

       example:
       compose(f,g)(x) <==> f(g(x))
    """
    funcs = reversed(funcs)
    f = funcs.next()
    for g in funcs:
        f = compose2(g, f)
    return f
