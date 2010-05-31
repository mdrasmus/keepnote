"""

    KeepNote
    Backward compatiability for configuration information

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
import shutil
from xml.etree import ElementTree

import keepnote
from keepnote import FS_ENCODING
from keepnote import xdg

OLD_USER_PREF_DIR = u"takenote"
OLD_USER_PREF_FILE = u"takenote.xml"
OLD_XDG_USER_EXTENSIONS_DIR = u"takenote/extensions"
OLD_XDG_USER_EXTENSIONS_DATA_DIR = u"takenote/extensions_data"


USER_PREF_DIR = u"keepnote"
USER_PREF_FILE = u"keepnote.xml"
USER_EXTENSIONS_DIR = u"extensions"
USER_EXTENSIONS_DATA_DIR = u"extensions_data"

XDG_USER_EXTENSIONS_DIR = u"keepnote/extensions"
XDG_USER_EXTENSIONS_DATA_DIR = u"keepnote/extensions_data"



def get_old_pref_dir1(home):
    """
    Returns old preference directory (type 1)
    $HOME/.takenote
    """
    return os.path.join(home, "." + OLD_USER_PREF_DIR)


def get_old_pref_dir2(home):
    """
    Returns old preference directory (type 2)
    $HOME/.config/takenote
    """
    return os.path.join(home, "config", OLD_USER_PREF_DIR)



def get_new_pref_dir(home):
    """
    Returns old preference directory (type 2)
    $HOME/.config/takenote
    """
    return os.path.join(home, "config", USER_PREF_DIR)


def get_home():
    """Return HOME directory"""
    home = keepnote.ensure_unicode(os.getenv(u"HOME"), FS_ENCODING)
    if home is None:
        raise EnvError("HOME environment variable must be specified")
    return home


def get_old_user_pref_dir(home=None):
    """Returns the directory of the application preference file"""
    
    p = keepnote.get_platform()
    if p == "unix" or p == "darwin":
        
        if home is None:
            home = get_home()
        old_dir = get_old_pref_dir1(home)

        if os.path.exists(old_dir):
            return old_dir
        else:
            return xdg.get_config_file(OLD_USER_PREF_DIR, default=True)

    elif p == "windows":
        appdata = keepnote.get_win_env("APPDATA")
        if appdata is None:
            raise keepnote.EnvError("APPDATA environment variable must be specified")
        return os.path.join(appdata, OLD_USER_PREF_DIR)

    else:
        raise Exception("unknown platform '%s'" % p)


def get_new_user_pref_dir(home=None):
    """Returns the directory of the application preference file"""
    
    p = keepnote.get_platform()
    if p == "unix" or p == "darwin":
        
        if home is None:
            home = get_home()
        return xdg.get_config_file(USER_PREF_DIR, default=True)

    elif p == "windows":
        appdata = keepnote.get_win_env("APPDATA")
        if appdata is None:
            raise keepnote.EnvError("APPDATA environment variable must be specified")
        return os.path.join(appdata, USER_PREF_DIR)

    else:
        raise Exception("unknown platform '%s'" % p)


def upgrade_user_pref_dir(old_user_pref_dir, new_user_pref_dir):
    """Moves preference data from old location to new one"""

    import sys
    
    # move user preference directory
    shutil.copytree(old_user_pref_dir, new_user_pref_dir)

    # rename takenote.xml to keepnote.xml
    oldfile = os.path.join(new_user_pref_dir, OLD_USER_PREF_FILE)
    newfile = os.path.join(new_user_pref_dir, USER_PREF_FILE)

    if os.path.exists(oldfile):
        os.rename(oldfile, newfile)
    
        # rename root xml tag
        tree = ElementTree.ElementTree(file=newfile)
        elm = tree.getroot()
        elm.tag = "keepnote"
        tree.write(newfile, encoding="UTF-8")

    # move over data files from .local/share/takenote
    if keepnote.get_platform() in ("unix", "darwin"):
        datadir = os.path.join(get_home(), ".local", "share", "takenote")
        
        old_ext_dir = os.path.join(datadir, "extensions")
        new_ext_dir = os.path.join(new_user_pref_dir, "extensions")    
        if not os.path.exists(new_ext_dir) and os.path.exists(old_ext_dir):
            shutil.copytree(old_ext_dir, new_ext_dir)

        old_ext_dir = os.path.join(datadir, "extensions_data")
        new_ext_dir = os.path.join(new_user_pref_dir, "extensions_data")    
        if not os.path.exists(new_ext_dir) and os.path.exists(old_ext_dir):
            shutil.copytree(old_ext_dir, new_ext_dir)
            
        


def check_old_user_pref_dir(home=None):
    """Upgrades user preference directory if it exists in an old format"""

    old_pref_dir = get_old_user_pref_dir(home)
    new_pref_dir = get_new_user_pref_dir(home)
    if not os.path.exists(new_pref_dir) and os.path.exists(old_pref_dir):
        upgrade_user_pref_dir(old_pref_dir, new_pref_dir)
        


