"""
    KeepNote
    Extension system
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
import imp
import sys

import keepnote
from keepnote.listening import Listeners

# globals
EXTENSION_EXT = ".kne"  # filename extension for KeepNote Extensions


class DependencyError (StandardError):
    """Exception for dependency error"""

    def __init__(self, ext, dep):
        self.ext = ext
        self.dep = dep


    def __str__(self):
        return "Extension '%s' has failed dependency %s" % (self.ext.key, self.dep)


#=============================================================================
# extension functions


def init_user_extensions(pref_dir=None, home=None):
    """Ensure users extensions are initialized
       Install defaults if needed"""

    if pref_dir is None:
        pref_dir = keepnote.get_user_pref_dir(home)

    extensions_dir = keepnote.get_user_extensions_dir(pref_dir)
    if not os.path.exists(extensions_dir):
        # make user extensions directory
        os.makedirs(extensions_dir, 0700)

    extensions_data_dir = keepnote.get_user_extensions_data_dir(pref_dir)
    if not os.path.exists(extensions_data_dir):
        # make user extensions data directory
        os.makedirs(extensions_data_dir, 0700)



def iter_extensions(extensions_dir):
    """Iterate through the extensions in directory"""

    for filename in os.listdir(extensions_dir):
        yield os.path.join(extensions_dir, filename)



def import_extension(app, name, filename):
    """Import an Extension"""

    filename2 = os.path.join(filename, "__init__.py")

    try:
        infile = open(filename2)
    except Exception, e:
        raise keepnote.KeepNotePreferenceError("cannot load extension '%s'" %
                                               filename, e)

    try:
        mod = imp.load_module(name, infile, filename2,
                              (".py", "rb", imp.PY_SOURCE))
        ext = mod.Extension(app)
        ext.key = name
        infile.close()
        return ext
                
    except Exception, e:
        infile.close()
        raise keepnote.KeepNotePreferenceError("cannot load extension '%s'" %
                                               filename, e)



def dependency_satisfied(ext, dep):
    """
    Checks whether an extension satisfies a dependency

    if ext is None, only the 'no' rel is checked
    """

    name, rel, version = dep

    if ext is None:
        return (rel == "no")

    if rel == ">":
        if not (ext.version > version): return False
    elif rel == ">=":
        if not (ext.version >= version): return False
    elif rel == "==":
        if not (ext.version == version): return False
    elif rel == "<=":
        if not (ext.version <= version): return False
    elif rel == "<":
        if not (ext.version < version): return False
    elif rel == "!=":
        if not (ext.version != version): return False

    return True


def is_extension_install_file(filename):
    """
    Returns True if file is an extension install file
    """
    return filename.endswith(EXTENSION_EXT)


class Extension (object):
    """KeepNote Extension"""

    version = (1, 0)
    key = ""
    name = "untitled"
    author = "no author"
    website = "http://rasm.ods.org/keepnote"
    description = "base extension"
    visible = True


    def __init__(self, app):
        
        self._app = app
        self._enabled = False
        self.type = "system"
        self.enabled = Listeners()


    def enable(self, enable):
        """Enable/disable extension"""

        # check dependencies
        self.check_depends()
        
        # mark extension as enabled
        self._enabled = enable
        
        # notify listeners
        self.enabled.notify(enable)
        
        # return whether the extension is enabled
        return self._enabled


    def is_enabled(self):
        """Returns True if extension is enabled"""
        return self._enabled


    def check_depends(self):
        """Checks whether dependencies are met.  Throws exception on failure"""
        for dep in self.get_depends():
            if not self._app.dependency_satisfied(dep):
                raise DependencyError(self, dep)


    def get_depends(self):
        """
        Returns dependencies of extension

        Dependencies returned as a list of tuples (NAME, REL, EXTRA)

        NAME is a string identify an extension (or 'keepnote' itself).
        EXTRA is an object whose type depends on REL

        REL is a string representing a relation.  Options are:

          Version relations.  For each of these values for REL, the EXTRA
          field is interpreted as VERSION (see below):
            '>='   the version must be greater than or equal to
            '>'    the version must be greater than
            '=='   the version must be exactly equal to
            '<='   the version must less than or equal to
            '<'    the version must be less than
            '!='   the version must not be equal to

          Other relations.  
            'no'   the extension must not exist.  EXTRA is None.


        Possible values for EXTRA:

          VERSION   This is a tuple representing a version number.
            ex: the tuple (0, 6, 1) represents version 0.6.1


        All dependencies must be met to enable an extension.  A extension
        name can appear more than once if several relations are required
        (such as specifying a range of valid version numbers).

        """

        return [("keepnote", ">=", (0, 6, 1))]

    #===============================
    # filesystem paths

    def get_base_dir(self, exist=True):
        """Returns the directory containing the extensions code"""
        path = self._app.get_extension_base_dir(self.key)
        if exist and not os.path.exists(path):
            os.makedirs(path)
        return path


    def get_data_dir(self, exist=True):
        """Returns the directory for storing data specific to this extension"""
        path = self._app.get_extension_data_dir(self.key)
        if exist and not os.path.exists(path):
            os.makedirs(path)
        return path

    def get_data_file(self, filename, exist=True):
        """
        Returns a full path to  a file within the extension's data directory
        """
        return os.path.join(self.get_data_dir(exist), filename)

