"""

    Simple implementation of the XDG Base Directory Specification

    http://standards.freedesktop.org/basedir-spec/basedir-spec-0.6.html

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

# python imports
import os
import sys

# constants
ENV_CONFIG = u"XDG_CONFIG_HOME"
ENV_CONFIG_DIRS = u"XDG_CONFIG_DIRS"
ENV_DATA = u"XDG_DATA_HOME"
ENV_DATA_DIRS = u"XDG_DATA_DIRS"

DEFAULT_CONFIG_DIR = u".config"
DEFAULT_CONFIG_DIRS = u"/etc/xdg"
DEFAULT_DATA_DIR = u".local/share"
DEFAULT_DATA_DIRS = u"/usr/local/share/:/usr/share/"

# global cache
g_config_dirs = None
g_data_dirs = None


class XdgError (StandardError):
    pass


FS_ENCODING = object()


def ensure_unicode(text, encoding="utf8"):
    """Ensures a string is unicode"""

    if text is None:
        return None

    if not isinstance(text, unicode):
        if encoding == FS_ENCODING:
            return unicode(text, sys.getfilesystemencoding())
        else:
            return unicode(text, encoding)
    return text


def get_config_dirs(home=None, cache=True):
    """
    Returns list of configuration directories for user

    home  -- alternative HOME directory
    cache -- if True, caches the result for future calls
    """

    global g_config_dirs

    # check cache
    if cache and g_config_dirs is not None:
        return g_config_dirs

    # get user config dir
    config = ensure_unicode(os.getenv(ENV_CONFIG), FS_ENCODING)
    if config is None:
        if home is None:
            home = ensure_unicode(os.getenv("HOME"), FS_ENCODING)
            if home is None:
                raise XdgError("HOME environment variable must be specified")
        config = os.path.join(home, DEFAULT_CONFIG_DIR)

    # get alternate user config dirs
    config_dirs = ensure_unicode(os.getenv(ENV_CONFIG_DIRS,
                                           DEFAULT_CONFIG_DIRS),
                                 FS_ENCODING)

    if config_dirs == "":
        config_dirs = DEFAULT_CONFIG_DIRS

    # make config path
    config_dirs = [config] + config_dirs.split(u":")

    if cache:
        g_config_dirs = config_dirs

    return config_dirs


def get_data_dirs(home=None, cache=True):
    """
    Returns list of data directories for user

    home  -- alternative HOME directory
    cache -- if True, caches the result for future calls
    """

    global g_data_dirs

    # check cache
    if cache and g_data_dirs is not None:
        return g_data_dirs

    # get user config dir
    data = ensure_unicode(os.getenv(ENV_DATA), FS_ENCODING)
    if data is None:
        if home is None:
            home = ensure_unicode(os.getenv("HOME"), FS_ENCODING)
            if home is None:
                raise XdgError("HOME environment variable must be specified")
        data = os.path.join(home, DEFAULT_DATA_DIR)

    # get alternate user config dirs
    data_dirs = ensure_unicode(os.getenv(ENV_DATA_DIRS, DEFAULT_DATA_DIRS),
                               FS_ENCODING)
    if data_dirs == "":
        data_dirs = DEFAULT_DATA_DIRS

    # make data path
    data_dirs = [data] + data_dirs.split(u":")

    if cache:
        g_data_dirs = data_dirs

    return data_dirs


def lookup_file(filename, paths, default=False):
    """
    Searches for a filename in a list of paths.
    Return None if file is not found
    """

    for path in paths:
        filename2 = os.path.join(path, filename)
        if os.path.exists(filename2):
            return filename2

    if default:
        return os.path.join(paths[0], filename)
    else:
        return None


def get_config_file(filename, config_dirs=None, default=False,
                    home=None, cache=True):
    """
    Lookup a config file from the config_path.
    Returns None is file is not found.

    config_dir  -- list of directories to search for file
    """
    if config_dirs is None:
        config_dirs = get_config_dirs(home=home, cache=cache)

    return lookup_file(filename, config_dirs, default)


def get_data_file(filename, data_dirs=None, default=False,
                  home=None, cache=True):
    """
    Lookup a config file from the config_path.
    Returns None is file is not found.

    config_dir  -- list of directories to search for file
    """
    if data_dirs is None:
        data_dirs = get_data_dirs(home=home, cache=cache)

    return lookup_file(filename, data_dirs, default)


def make_config_dir(dirname, config_dirs=None,
                    home=None, cache=True):
    """
    Make a configuration directory
    """
    if config_dirs is None:
        config_dirs = get_config_dirs(home=home, cache=cache)
    config_dir = os.path.join(config_dirs[0], dirname)

    if not os.path.exists(config_dir):
        os.makedirs(config_dir, mode=0700)


def make_data_dir(dirname, data_dirs=None,
                  home=None, cache=True):
    """
    Make a data directory
    """
    if data_dirs is None:
        data_dirs = get_data_dirs(home=home, cache=cache)
    data_dir = os.path.join(data_dirs[0], dirname)

    if not os.path.exists(data_dir):
        os.makedirs(data_dir, mode=0700)
