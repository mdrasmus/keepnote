"""
    KeepNote
    Module for KeepNote

    Basic backend data structures for KeepNote and NoteBooks
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
import os
import shutil
import sys
import time
import re
import subprocess
import tempfile
import traceback
import uuid
import zipfile
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.elementtree.ElementTree as ET


# work around pygtk changing default encoding
DEFAULT_ENCODING = sys.getdefaultencoding()
FS_ENCODING = sys.getfilesystemencoding()

# keepnote imports
from keepnote import extension
from keepnote import mswin
from keepnote import orderdict
from keepnote import plist
from keepnote import safefile
from keepnote.listening import Listeners
from keepnote.notebook import \
    NoteBookError, \
    get_unique_filename_list
import keepnote.notebook as notebooklib
import keepnote.notebook.connection
import keepnote.notebook.connection.fs
import keepnote.notebook.connection.http
from keepnote.pref import Pref
import keepnote.timestamp
import keepnote.trans
from keepnote.trans import GETTEXT_DOMAIN
import keepnote.xdg


#=============================================================================
# modules needed by builtin extensions
# these are imported here, so that py2exe can auto-discover them

import base64
import htmlentitydefs
from keepnote import tarfile
import random
import sgmllib
import string
import xml.dom.minidom
import xml.sax.saxutils

# make pyflakes ignore these used modules
GETTEXT_DOMAIN
base64
get_unique_filename_list
htmlentitydefs
random
sgmllib
string
tarfile
xml

# import screenshot so that py2exe discovers it
try:
    import mswin.screenshot
except ImportError:
    pass


#=============================================================================
# globals / constants

PROGRAM_NAME = u"KeepNote"
PROGRAM_VERSION_MAJOR = 0
PROGRAM_VERSION_MINOR = 7
PROGRAM_VERSION_RELEASE = 9
PROGRAM_VERSION = (PROGRAM_VERSION_MAJOR,
                   PROGRAM_VERSION_MINOR,
                   PROGRAM_VERSION_RELEASE)

if PROGRAM_VERSION_RELEASE != 0:
    PROGRAM_VERSION_TEXT = "%d.%d.%d" % (PROGRAM_VERSION_MAJOR,
                                         PROGRAM_VERSION_MINOR,
                                         PROGRAM_VERSION_RELEASE)
else:
    PROGRAM_VERSION_TEXT = "%d.%d" % (PROGRAM_VERSION_MAJOR,
                                      PROGRAM_VERSION_MINOR)

WEBSITE = u"http://keepnote.org"
LICENSE_NAME = u"GPL version 2"
COPYRIGHT = u"Copyright Matt Rasmussen 2011."
TRANSLATOR_CREDITS = (
    u"Chinese: hu dachuan <hdccn@sina.com>\n"
    u"French: tb <thibaut.bethune@gmail.com>\n"
    u"French: Sebastien KALT <skalt@throka.org>\n"
    u"German: Jan Rimmek <jan.rimmek@mhinac.de>\n"
    u"Japanese: Toshiharu Kudoh <toshi.kd2@gmail.com>\n"
    u"Italian: Davide Melan <davide.melan@gmail.com>\n"
    u"Polish: Bernard Baraniewski <raznaya2010(at)rambler(dot)ru>\n"
    u"Russian: Hikiko Mori <hikikomori.dndz@gmail.com>\n"
    u"Spanish: Klemens Hackel <click3d at linuxmail (dot) org>\n"
    u"Slovak: Slavko <linux@slavino.sk>\n"
    u"Swedish: Morgan Antonsson <morgan.antonsson@gmail.com>\n"
    u"Turkish: Yuce Tekol <yucetekol@gmail.com>\n"
)


BASEDIR = os.path.dirname(unicode(__file__, FS_ENCODING))
PLATFORM = None

USER_PREF_DIR = u"keepnote"
USER_PREF_FILE = u"keepnote.xml"
USER_LOCK_FILE = u"lockfile"
USER_ERROR_LOG = u"error-log.txt"
USER_EXTENSIONS_DIR = u"extensions"
USER_EXTENSIONS_DATA_DIR = u"extensions_data"
PORTABLE_FILE = u"portable.txt"


#=============================================================================
# application resources

# TODO: cleanup, make get/set_basedir symmetrical

def get_basedir():
    return os.path.dirname(unicode(__file__, FS_ENCODING))


def set_basedir(basedir):
    global BASEDIR
    if basedir is None:
        BASEDIR = get_basedir()
    else:
        BASEDIR = basedir
    keepnote.trans.set_local_dir(get_locale_dir())


def get_resource(*path_list):
    return os.path.join(BASEDIR, *path_list)


#=============================================================================
# common functions

def get_platform():
    """Returns a string for the current platform"""
    global PLATFORM

    if PLATFORM is None:
        p = sys.platform
        if p == 'darwin':
            PLATFORM = 'darwin'
        elif p.startswith('win'):
            PLATFORM = 'windows'
        else:
            PLATFORM = 'unix'

    return PLATFORM


def is_url(text):
    """Returns True is text is a url"""
    return re.match("^[^:]+://", text) is not None


def ensure_unicode(text, encoding="utf8"):
    """Ensures a string is unicode"""

    # let None's pass through
    if text is None:
        return None

    # make sure text is unicode
    if not isinstance(text, unicode):
        return unicode(text, encoding)
    return text


def unicode_gtk(text):
    """
    Converts a string from gtk (utf8) to unicode

    All strings from the pygtk API are returned as byte strings (str)
    encoded as utf8.  KeepNote has the convention to keep all strings as
    unicode internally.  So strings from pygtk must be converted to unicode
    immediately.

    Note: pygtk can accept either unicode or utf8 encoded byte strings.
    """
    if text is None:
        return None
    return unicode(text, "utf8")


def print_error_log_header(out=None):
    """Display error log header"""
    if out is None:
        out = sys.stderr

    out.write("==============================================\n"
              "%s %s: %s\n" % (keepnote.PROGRAM_NAME,
                               keepnote.PROGRAM_VERSION_TEXT,
                               time.asctime()))


def print_runtime_info(out=None):
    """Display runtime information"""

    if out is None:
        out = sys.stderr

    import keepnote

    out.write("Python runtime\n"
              "--------------\n"
              "sys.version=" + sys.version+"\n"
              "sys.getdefaultencoding()="+DEFAULT_ENCODING+"\n"
              "sys.getfilesystemencoding()="+FS_ENCODING+"\n"
              "PYTHONPATH="
              "  "+"\n  ".join(sys.path)+"\n"
              "\n"

              "Imported libs\n"
              "-------------\n"
              "keepnote: " + keepnote.__file__+"\n")
    try:
        import gtk
        out.write("gtk: " + gtk.__file__+"\n")
        out.write("gtk.gtk_version: "+repr(gtk.gtk_version)+"\n")
    except:
        out.write("gtk: NOT PRESENT\n")

    from keepnote.notebook.connection.fs.index import sqlite
    out.write("sqlite: " + sqlite.__file__+"\n"
              "sqlite.version: " + sqlite.version+"\n"
              "sqlite.sqlite_version: " + sqlite.sqlite_version+"\n"
              "sqlite.fts3: " + str(test_fts3())+"\n")

    try:
        import gtkspell
        out.write("gtkspell: " + gtkspell.__file__+"\n")
    except ImportError:
        out.write("gtkspell: NOT PRESENT\n")
    out.write("\n")


def test_fts3():
    from keepnote.notebook.connection.fs.index import sqlite

    con = sqlite.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE fts3test USING fts3(col TEXT);")
    except:
        return False
    finally:
        con.close()
    return True


#=============================================================================
# locale functions

def translate(message):
    """Translate a string"""
    return keepnote.trans.translate(message)


def get_locale_dir():
    """Returns KeepNote's locale directory"""
    return get_resource(u"rc", u"locale")


_ = translate


#=============================================================================
# preference filenaming scheme


def get_home():
    """Returns user's HOME directory"""
    home = ensure_unicode(os.getenv(u"HOME"), FS_ENCODING)
    if home is None:
        raise EnvError("HOME environment variable must be specified")
    return home


def get_user_pref_dir(home=None):
    """Returns the directory of the application preference file"""

    p = get_platform()
    if p == "unix" or p == "darwin":
        if home is None:
            home = get_home()
        return keepnote.xdg.get_config_file(USER_PREF_DIR, default=True)

    elif p == "windows":
        # look for portable config
        if os.path.exists(os.path.join(BASEDIR, PORTABLE_FILE)):
            return os.path.join(BASEDIR, USER_PREF_DIR)

        # otherwise, use application data dir
        appdata = get_win_env("APPDATA")
        if appdata is None:
            raise EnvError("APPDATA environment variable must be specified")
        return os.path.join(appdata, USER_PREF_DIR)

    else:
        raise Exception("unknown platform '%s'" % p)


def get_user_extensions_dir(pref_dir=None, home=None):
    """Returns user extensions directory"""

    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)
    return os.path.join(pref_dir, USER_EXTENSIONS_DIR)


def get_user_extensions_data_dir(pref_dir=None, home=None):
    """Returns user extensions data directory"""

    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)
    return os.path.join(pref_dir, USER_EXTENSIONS_DATA_DIR)


def get_system_extensions_dir():
    """Returns system-wide extensions directory"""
    return os.path.join(BASEDIR, u"extensions")


def get_user_documents(home=None):
    """Returns the directory of the user's documents"""
    p = get_platform()
    if p == "unix" or p == "darwin":
        if home is None:
            home = get_home()
        return home

    elif p == "windows":
        return unicode(mswin.get_my_documents(), FS_ENCODING)

    else:
        return u""


def get_user_pref_file(pref_dir=None, home=None):
    """Returns the filename of the application preference file"""
    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)
    return os.path.join(pref_dir, USER_PREF_FILE)


def get_user_lock_file(pref_dir=None, home=None):
    """Returns the filename of the application lock file"""
    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)
    return os.path.join(pref_dir, USER_LOCK_FILE)


def get_user_error_log(pref_dir=None, home=None):
    """Returns a file for the error log"""
    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)
    return os.path.join(pref_dir, USER_ERROR_LOG)


def get_win_env(key):
    """Returns a windows environment variable"""
    # try both encodings
    try:
        return ensure_unicode(os.getenv(key), DEFAULT_ENCODING)
    except UnicodeDecodeError:
        return ensure_unicode(os.getenv(key), FS_ENCODING)


#=============================================================================
# preference/extension initialization

def init_user_pref_dir(pref_dir=None, home=None):
    """Initializes the application preference file"""

    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)

    # make directory
    if not os.path.exists(pref_dir):
        os.makedirs(pref_dir, 0700)

    # init empty pref file
    pref_file = get_user_pref_file(pref_dir)
    if not os.path.exists(pref_file):
        out = open(pref_file, "w")
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        out.write("<keepnote>\n")
        out.write("</keepnote>\n")
        out.close()

    # init error log
    init_error_log(pref_dir)

    # init user extensions
    extension.init_user_extensions(pref_dir)


def init_error_log(pref_dir=None, home=None):
    """Initialize the error log"""

    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)

    error_log = get_user_error_log(pref_dir)
    if not os.path.exists(error_log):
        error_dir = os.path.dirname(error_log)
        if not os.path.exists(error_dir):
            os.makedirs(error_dir)
        open(error_log, "a").close()


def log_error(error=None, tracebk=None, out=None):
    """Write an exception error to the error log"""

    if out is None:
        out = sys.stderr

    if error is None:
        ty, error, tracebk = sys.exc_info()

    try:
        out.write("\n")
        traceback.print_exception(type(error), error, tracebk, file=out)
        out.flush()
    except UnicodeEncodeError:
        out.write(error.encode("ascii", "replace"))


def log_message(message, out=None):
    """Write a message to the error log"""

    if out is None:
        out = sys.stderr
    try:
        out.write(message)
    except UnicodeEncodeError:
        out.write(message.encode("ascii", "replace"))
    out.flush()


#=============================================================================
# Exceptions


class EnvError (StandardError):
    """Exception that occurs when environment variables are ill-defined"""

    def __init__(self, msg, error=None):
        StandardError.__init__(self)
        self.msg = msg
        self.error = error

    def __str__(self):
        if self.error:
            return str(self.error) + "\n" + self.msg
        else:
            return self.msg


class KeepNoteError (StandardError):
    def __init__(self, msg, error=None):
        StandardError.__init__(self, msg)
        self.msg = msg
        self.error = error

    def __repr__(self):
        if self.error:
            return str(self.error) + "\n" + self.msg
        else:
            return self.msg

    def __str__(self):
        return self.msg


class KeepNotePreferenceError (StandardError):
    """Exception that occurs when manipulating preferences"""

    def __init__(self, msg, error=None):
        StandardError.__init__(self)
        self.msg = msg
        self.error = error

    def __str__(self):
        if self.error:
            return str(self.error) + "\n" + self.msg
        else:
            return self.msg


#=============================================================================
# Preference data structures

class ExternalApp (object):
    """
    Class represents the information needed for calling an external application
    """

    def __init__(self, key, title, prog, args=[]):
        self.key = key
        self.title = title
        self.prog = prog
        self.args = args


DEFAULT_EXTERNAL_APPS = [
    ExternalApp("file_launcher", "File Launcher", u""),
    ExternalApp("web_browser", "Web Browser", u""),
    ExternalApp("file_explorer", "File Explorer", u""),
    ExternalApp("text_editor", "Text Editor", u""),
    ExternalApp("image_editor", "Image Editor", u""),
    ExternalApp("image_viewer", "Image Viewer", u""),
    ExternalApp("screen_shot", "Screen Shot", u"")
]


def get_external_app_defaults():
    if get_platform() == "windows":
        files = ensure_unicode(
            os.environ.get(u"PROGRAMFILES", u"C:\\Program Files"), FS_ENCODING)

        return [
            ExternalApp("file_launcher", "File Launcher", u"explorer.exe"),
            ExternalApp("web_browser", "Web Browser",
                        files + u"\\Internet Explorer\\iexplore.exe"),
            ExternalApp("file_explorer", "File Explorer", u"explorer.exe"),
            ExternalApp("text_editor", "Text Editor",
                        files + u"\\Windows NT\\Accessories\\wordpad.exe"),
            ExternalApp("image_editor", "Image Editor", u"mspaint.exe"),
            ExternalApp("image_viewer", "Image Viewer",
                        files + u"\\Internet Explorer\\iexplore.exe"),
            ExternalApp("screen_shot", "Screen Shot", "")
        ]

    elif get_platform() == "unix":
        return [
            ExternalApp("file_launcher", "File Launcher", u"xdg-open"),
            ExternalApp("web_browser", "Web Browser", u""),
            ExternalApp("file_explorer", "File Explorer", u""),
            ExternalApp("text_editor", "Text Editor", u""),
            ExternalApp("image_editor", "Image Editor", u""),
            ExternalApp("image_viewer", "Image Viewer", u"display"),
            ExternalApp("screen_shot", "Screen Shot", u"import")
        ]
    else:
        return DEFAULT_EXTERNAL_APPS


class KeepNotePreferences (Pref):
    """Preference data structure for the KeepNote application"""

    def __init__(self, pref_dir=None, home=None):
        Pref.__init__(self)
        if pref_dir is None:
            self._pref_dir = get_user_pref_dir(home)
        else:
            self._pref_dir = pref_dir

        # listener
        self.changed = Listeners()
        #self.changed.add(self._on_changed)

    def get_pref_dir(self):
        """Returns preference directory"""
        return self._pref_dir

    #def _on_changed(self):
    #    """Listener for preference changes"""
    #    self.write()

    #=========================================
    # Input/Output

    def read(self):
        """Read preferences from file"""

        # ensure preference file exists
        if not os.path.exists(get_user_pref_file(self._pref_dir)):
            # write default
            try:
                init_user_pref_dir(self._pref_dir)
                self.write()
            except Exception, e:
                raise KeepNotePreferenceError(
                    "Cannot initialize preferences", e)

        try:
            # read preferences xml
            tree = ET.ElementTree(
                file=get_user_pref_file(self._pref_dir))

            # parse xml
            # check tree structure matches current version
            root = tree.getroot()
            if root.tag == "keepnote":
                p = root.find("pref")
                if p is None:
                    # convert from old preference version
                    import keepnote.compat.pref as old
                    old_pref = old.KeepNotePreferences()
                    old_pref.read(get_user_pref_file(self._pref_dir))
                    data = old_pref._get_data()
                else:
                    # get data object from xml
                    d = p.find("dict")
                    if d is not None:
                        data = plist.load_etree(d)
                    else:
                        data = orderdict.OrderDict()

                # set data
                self._data.clear()
                self._data.update(data)
        except Exception, e:
            raise KeepNotePreferenceError("Cannot read preferences", e)

        # notify listeners
        self.changed.notify()

    def write(self):
        """Write preferences to file"""

        try:
            if not os.path.exists(self._pref_dir):
                init_user_pref_dir(self._pref_dir)

            out = safefile.open(get_user_pref_file(self._pref_dir), "w",
                                codec="utf-8")
            out.write(u'<?xml version="1.0" encoding="UTF-8"?>\n'
                      u'<keepnote>\n'
                      u'<pref>\n')
            plist.dump(self._data, out, indent=4, depth=4)
            out.write(u'</pref>\n'
                      u'</keepnote>\n')

            out.close()

        except (IOError, OSError), e:
            log_error(e, sys.exc_info()[2])
            raise NoteBookError(_("Cannot save preferences"), e)


#=============================================================================
# Application class


class ExtensionEntry (object):
    """An entry for an Extension in the KeepNote application"""

    def __init__(self, filename, ext_type, ext):
        self.filename = filename
        self.ext_type = ext_type
        self.ext = ext

    def get_key(self):
        return os.path.basename(self.filename)


class AppCommand (object):
    """Application Command"""

    def __init__(self, name, func=lambda app, args: None,
                 metavar="", help=""):
        self.name = name
        self.func = func
        self.metavar = metavar
        self.help = help


class KeepNote (object):
    """KeepNote application class"""

    def __init__(self, basedir=None, pref_dir=None):

        # base directory of keepnote library
        if basedir is not None:
            set_basedir(basedir)
        self._basedir = BASEDIR

        # load application preferences
        self.pref = KeepNotePreferences(pref_dir)
        self.pref.changed.add(self._on_pref_changed)

        self.id = None

        # list of registered application commands
        self._commands = {}

        # list of opened notebooks
        self._notebooks = {}
        self._notebook_count = {}  # notebook ref counts

        # default protocols for notebooks
        self._conns = keepnote.notebook.connection.NoteBookConnections()
        self._conns.add(
            "file", keepnote.notebook.connection.fs.NoteBookConnectionFS)
        self._conns.add(
            "http", keepnote.notebook.connection.http.NoteBookConnectionHttp)

        # external apps
        self._external_apps = []
        self._external_apps_lookup = {}

        # set of registered extensions for this application
        self._extension_paths = []
        self._extensions = {}
        self._disabled_extensions = []

        # listeners
        self._listeners = {}

    def init(self):
        """Initialize from preferences saved on disk"""

        # read preferences
        self.pref.read()
        self.load_preferences()

        # init extension paths
        self._extension_paths = [
            (get_system_extensions_dir(), "system"),
            (get_user_extensions_dir(self.get_pref_dir()), "user")]

        # initialize all extensions
        self.init_extensions()

    def load_preferences(self):
        """Load information from preferences"""

        self.language = self.pref.get("language", default="")
        self.set_lang()

        # setup id
        self.id = self.pref.get("id", default="")
        if self.id == "":
            self.id = str(uuid.uuid4())
            self.pref.set("id", self.id)

        # TODO: move to gui app?
        # set default timestamp formats
        self.pref.get(
            "timestamp_formats",
            default=dict(keepnote.timestamp.DEFAULT_TIMESTAMP_FORMATS))

        # external apps
        self._load_external_app_preferences()

        # extensions
        self._disabled_extensions = self.pref.get(
            "extension_info", "disabled", default=[])
        self.pref.get("extensions", define=True)

    def save_preferences(self):
        """Save information into preferences"""

        # language
        self.pref.set("language", self.language)

        # external apps
        self.pref.set("external_apps", [
            {"key": app.key,
             "title": app.title,
             "prog": app.prog,
             "args": app.args}
            for app in self._external_apps])

        # extensions
        self.pref.set("extension_info", {
            "disabled": self._disabled_extensions[:]
            })

        # save to disk
        self.pref.write()

    def _on_pref_changed(self):
        """Callback for when application preferences change"""
        self.load_preferences()

    def set_lang(self):
        """Set the language based on preference"""
        keepnote.trans.set_lang(self.language)

    def error(self, text, error=None, tracebk=None):
        """Display an error message"""
        keepnote.log_message(text)
        if error is not None:
            keepnote.log_error(error, tracebk)

    def quit(self):
        """Stop the application"""

        if self.pref.get("use_last_notebook", default=False):
            self.pref.set("default_notebooks",
                          [n.get_path() for n in self.iter_notebooks()])

        self.save_preferences()

    def get_default_path(self, name):
        """Returns a default path for saving/reading files"""
        return self.pref.get("default_paths", name,
                             default=get_user_documents())

    def set_default_path(self, name, path):
        """Sets the default path for saving/reading files"""
        self.pref.set("default_paths", name, path)

    def get_pref_dir(self):
        return self.pref.get_pref_dir()

    #==================================
    # Notebooks

    def open_notebook(self, filename, window=None, task=None):
        """Open a new notebook"""

        try:
            conn = self._conns.get(filename)
            notebook = notebooklib.NoteBook()
            notebook.load(filename, conn)
        except Exception:
            return None
        return notebook

    def close_notebook(self, notebook):
        """Close notebook"""

        if self.has_ref_notebook(notebook):
            self.unref_notebook(notebook)

    def close_all_notebook(self, notebook, save=True):
        """Close all instances of a notebook"""

        try:
            notebook.close(save)
        except:
            keepnote.log_error()

        notebook.closing_event.remove(self._on_closing_notebook)
        del self._notebook_count[notebook]

        for key, val in self._notebooks.iteritems():
            if val == notebook:
                del self._notebooks[key]
                break

    def _on_closing_notebook(self, notebook, save):
        """
        Callback for when notebook is about to close
        """
        pass

    def get_notebook(self, filename, window=None, task=None):
        """
        Returns a an opened notebook referenced by filename

        Open a new notebook if it is not already opened.
        """

        try:
            filename = notebooklib.normalize_notebook_dirname(
                filename, longpath=False)
            filename = os.path.realpath(filename)
        except:
            pass

        if filename not in self._notebooks:
            notebook = self.open_notebook(filename, window, task=task)
            if notebook is None:
                return None

            # perform bookkeeping
            self._notebooks[filename] = notebook
            notebook.closing_event.add(self._on_closing_notebook)
            self.ref_notebook(notebook)
        else:
            notebook = self._notebooks[filename]
            self.ref_notebook(notebook)

        return notebook

    def ref_notebook(self, notebook):
        if notebook not in self._notebook_count:
            self._notebook_count[notebook] = 1
        else:
            self._notebook_count[notebook] += 1

    def unref_notebook(self, notebook):
        self._notebook_count[notebook] -= 1

        # close if refcount is zero
        if self._notebook_count[notebook] == 0:
            self.close_all_notebook(notebook)

    def has_ref_notebook(self, notebook):
        return notebook in self._notebook_count

    def iter_notebooks(self):
        """Iterate through open notebooks"""
        return self._notebooks.itervalues()

    def save_notebooks(self, silent=False):
        """Save all opened notebooks"""

        # save all the notebooks
        for notebook in self._notebooks.itervalues():
            notebook.save()

    def get_node(self, nodeid):
        """Returns a node with 'nodeid' from any of the opened notebooks"""

        for notebook in self._notebooks.itervalues():
            node = notebook.get_node_by_id(nodeid)
            if node is not None:
                return node

        return None

    def save(self, silent=False):
        """Save notebooks and preferences"""

        self.save_notebooks()

        self.save_preferences()

    #================================
    # listeners

    def get_listeners(self, key):
        listeners = self._listeners.get(key, None)
        if listeners is None:
            listeners = Listeners()
            self._listeners[key] = listeners
        return listeners

    #================================
    # external apps

    def _load_external_app_preferences(self):

        # external apps
        self._external_apps = []
        for app in self.pref.get("external_apps", default=[]):
            if "key" not in app:
                continue
            app2 = ExternalApp(app["key"],
                               app.get("title", ""),
                               app.get("prog", ""),
                               app.get("args", ""))
            self._external_apps.append(app2)

        # make lookup
        self._external_apps_lookup = {}
        for app in self._external_apps:
            self._external_apps_lookup[app.key] = app

        # add default programs
        lst = get_external_app_defaults()
        for defapp in lst:
            if defapp.key not in self._external_apps_lookup:
                self._external_apps.append(defapp)
                self._external_apps_lookup[defapp.key] = defapp

        # place default apps first
        lookup = dict((x.key, i) for i, x in enumerate(DEFAULT_EXTERNAL_APPS))
        top = len(DEFAULT_EXTERNAL_APPS)
        self._external_apps.sort(key=lambda x: (lookup.get(x.key, top), x.key))

    def get_external_app(self, key):
        """Return an external application by its key name"""
        app = self._external_apps_lookup.get(key, None)
        if app == "":
            app = None
        return app

    def iter_external_apps(self):
        return iter(self._external_apps)

    def run_external_app(self, app_key, filename, wait=False):
        """Runs a registered external application on a file"""

        app = self.get_external_app(app_key)

        if app is None or app.prog == "":
            if app:
                raise KeepNoteError(
                    _("Must specify '%s' program in Helper Applications" %
                      app.title))
            else:
                raise KeepNoteError(
                    _("Must specify '%s' program in Helper Applications" %
                      app_key))

        # build command arguments
        cmd = [app.prog] + app.args
        if "%f" not in cmd:
            cmd.append(filename)
        else:
            for i in xrange(len(cmd)):
                if cmd[i] == "%f":
                    cmd[i] = filename

        # create proper encoding
        cmd = map(lambda x: unicode(x), cmd)
        if get_platform() == "windows":
            cmd = [x.encode('mbcs') for x in cmd]
        else:
            cmd = [x.encode(FS_ENCODING) for x in cmd]

        # execute command
        try:
            proc = subprocess.Popen(cmd)
        except OSError, e:
            raise KeepNoteError(
                _(u"Error occurred while opening file with %s.\n\n"
                  u"program: '%s'\n\n"
                  u"file: '%s'\n\n"
                  u"error: %s")
                % (app.title, app.prog, filename, unicode(e)), e)

        # wait for process to return
        # TODO: perform waiting in gtk loop
        # NOTE: I do not wait for any program yet
        if wait:
            return proc.wait()

    def run_external_app_node(self, app_key, node, kind, wait=False):
        """Runs an external application on a node"""

        if kind == "dir":
            filename = node.get_path()
        else:
            if node.get_attr("content_type") == notebooklib.CONTENT_TYPE_PAGE:
                # get html file
                filename = node.get_data_file()

            elif node.get_attr("content_type") == notebooklib.CONTENT_TYPE_DIR:
                # get node dir
                filename = node.get_path()

            elif node.has_attr("payload_filename"):
                # get payload file
                filename = node.get_file(node.get_attr("payload_filename"))
            else:
                raise KeepNoteError(_("Unable to determine note type."))

        #if not filename.startswith("http://"):
        #    filename = os.path.realpath(filename)

        self.run_external_app(app_key, filename, wait=wait)

    def open_webpage(self, url):
        """View a node with an external web browser"""

        if url:
            self.run_external_app("web_browser", url)

    def take_screenshot(self, filename):
        """Take a screenshot and save it to 'filename'"""

        # make sure filename is unicode
        filename = ensure_unicode(filename, "utf-8")

        if get_platform() == "windows":
            # use win32api to take screenshot
            # create temp file

            f, imgfile = tempfile.mkstemp(u".bmp", filename)
            os.close(f)
            mswin.screenshot.take_screenshot(imgfile)
        else:
            # use external app for screen shot
            screenshot = self.get_external_app("screen_shot")
            if screenshot is None or screenshot.prog == "":
                raise Exception(
                    _("You must specify a Screen Shot program in "
                      "Application Options"))

            # create temp file
            f, imgfile = tempfile.mkstemp(".png", filename)
            os.close(f)

            proc = subprocess.Popen([screenshot.prog, imgfile])
            if proc.wait() != 0:
                raise OSError("Exited with error")

        if not os.path.exists(imgfile):
            # catch error if image is not created
            raise Exception(
                _("The screenshot program did not create the necessary "
                  "image file '%s'") % imgfile)

        return imgfile

    #================================
    # commands

    def get_command(self, command_name):
        """Returns a command of the given name 'command_name'"""
        return self._commands.get(command_name, None)

    def get_commands(self):
        """Returns a list of all registered commands"""
        return self._commands.values()

    def add_command(self, command):
        """Adds a command to the application"""
        if command.name in self._commands:
            raise Exception(_("command '%s' already exists") % command.name)

        self._commands[command.name] = command

    def remove_command(self, command_name):
        """Removes a command from the application"""
        if command_name in self._commands:
            del self._commands[command_name]

    #================================
    # extensions

    def init_extensions(self):
        """Enable all extensions"""

        # remove all existing extensions
        self._clear_extensions()

        # scan for extensions
        self._scan_extension_paths()

        # import all extensions
        self._import_all_extensions()

        # enable those extensions that have their dependencies met
        for ext in self.get_imported_extensions():
            # enable extension
            try:
                if ext.key not in self._disabled_extensions:
                    log_message(_("enabling extension '%s'\n") % ext.key)
                    ext.enable(True)

            except extension.DependencyError, e:
                # could not enable due to failed dependency
                log_message(_("  skipping extension '%s':\n") % ext.key)
                for dep in ext.get_depends():
                    if not self.dependency_satisfied(dep):
                        log_message(_("    failed dependency: %s\n") %
                                    repr(dep))

            except Exception, e:
                # unknown error
                log_error(e, sys.exc_info()[2])

    def _clear_extensions(self):
        """Disable and unregister all extensions for the app"""

        # disable all enabled extensions
        for ext in list(self.get_enabled_extensions()):
            ext.disable()

        # reset registered extensions list
        self._extensions = {
            "keepnote": ExtensionEntry("", "system", KeepNoteExtension(self))}

    def _scan_extension_paths(self):
        """Scan all extension paths"""
        for path, ext_type in self._extension_paths:
            self._scan_extension_path(path, ext_type)

    def _scan_extension_path(self, extensions_path, ext_type):
        """
        Scan extensions directory and register extensions with app

        extensions_path -- path for extensions
        ext_type        -- "user"/"system"
        """
        for filename in extension.scan_extensions_dir(extensions_path):
            self.add_extension(filename, ext_type)

    def add_extension(self, filename, ext_type):
        """Add an extension filename to the app's extension entries"""
        entry = ExtensionEntry(filename, ext_type, None)
        self._extensions[entry.get_key()] = entry
        return entry

    def remove_extension(self, ext_key):
        """Remove an extension entry"""

       # retrieve information about extension
        entry = self._extensions.get(ext_key, None)
        if entry:
            if entry.ext:
                # disable extension
                entry.ext.enable(False)

            # unregister extension from app
            del self._extensions[ext_key]

    def get_extension(self, name):
        """Get an extension module by name"""

        # return None if extension name is unknown
        if name not in self._extensions:
            return None

        # get extension information
        entry = self._extensions[name]

        # load if first use
        if entry.ext is None:
            self._import_extension(entry)

        return entry.ext

    def get_installed_extensions(self):
        """Iterates through installed extensions"""
        return self._extensions.iterkeys()

    def get_imported_extensions(self):
        """Iterates through imported extensions"""
        for entry in self._extensions.values():
            if entry.ext is not None:
                yield entry.ext

    def get_enabled_extensions(self):
        """Iterates through enabled extensions"""
        for ext in self.get_imported_extensions():
            if ext.is_enabled():
                yield ext

    def _import_extension(self, entry):
        """Import an extension from an extension entry"""
        try:
            entry.ext = extension.import_extension(
                self, entry.get_key(), entry.filename)
        except KeepNotePreferenceError, e:
            log_error(e, sys.exc_info()[2])
            return None

        entry.ext.type = entry.ext_type
        entry.ext.enabled.add(
            lambda e: self.on_extension_enabled(entry.ext, e))
        return entry.ext

    def _import_all_extensions(self):
        """Import all extensions"""
        for entry in self._extensions.values():
            # load if first use
            if entry.ext is None:
                self._import_extension(entry)

    def dependency_satisfied(self, dep):
        """
        Returns True if dependency 'dep' is satisfied by registered extensions
        """
        ext = self.get_extension(dep[0])
        return extension.dependency_satisfied(ext, dep)

    def dependencies_satisfied(self, depends):
        """Returns True if dependencies 'depends' are satisfied"""

        for dep in depends:
            ext = self.get_extension(dep[0])
            if ext is None or not extension.dependency_satisfied(ext, dep):
                return False
        return True

    def on_extension_enabled(self, ext, enabled):
        """Callback for when extension is enabled"""

        # update user preference on which extensions are disabled
        if enabled:
            if ext.key in self._disabled_extensions:
                self._disabled_extensions.remove(ext.key)
        else:
            if ext.key not in self._disabled_extensions:
                self._disabled_extensions.append(ext.key)

    def install_extension(self, filename):
        """Install a new extension from package 'filename'"""

        log_message(_("Installing extension '%s'\n") % filename)

        userdir = get_user_extensions_dir(self.get_pref_dir())

        newfiles = []
        try:
            # unzip and record new files
            for fn in unzip(filename, userdir):
                newfiles.append(fn)

            # rescan user extensions
            exts = set(self._extensions.keys())
            self._scan_extension_path(userdir, "user")

            # find new extensions
            new_names = set(self._extensions.keys()) - exts
            new_exts = [self.get_extension(name) for name in new_names]

        except Exception, e:
            self.error(_("Unable to install extension '%s'") % filename,
                       e, tracebk=sys.exc_info()[2])

            # delete newfiles
            for newfile in newfiles:
                try:
                    keepnote.log_message(_("Removing file '%s'") % newfile)
                    os.remove(newfile)
                except:
                    # delete may fail, continue
                    pass

            return []

        # enable new extensions
        log_message(_("Enabling new extensions:\n"))
        for ext in new_exts:
            log_message(_("enabling extension '%s'\n") % ext.key)
            ext.enable(True)

        return new_exts

    def uninstall_extension(self, ext_key):
        """Uninstall an extension"""

        # retrieve information about extension
        entry = self._extensions.get(ext_key, None)

        if entry is None:
            self.error(
                _("Unable to uninstall unknown extension '%s'.") % ext_key)
            return False

        # cannot uninstall system extensions
        if entry.ext_type != "user":
            self.error(_("KeepNote can only uninstall user extensions"))
            return False

        # remove extension from runtime
        self.remove_extension(ext_key)

        # delete extension from filesystem
        try:
            shutil.rmtree(entry.filename)
        except OSError:
            self.error(
                _("Unable to uninstall extension.  Do not have permission."))
            return False

        return True

    def can_uninstall(self, ext):
        """Return True if extension can be uninstalled"""
        return ext.type != "system"

    def get_extension_base_dir(self, extkey):
        """Get base directory of an extension"""
        return self._extensions[extkey].filename

    def get_extension_data_dir(self, extkey):
        """Get the data directory of an extension"""
        return os.path.join(
            get_user_extensions_data_dir(self.get_pref_dir()), extkey)


def unzip(filename, outdir):
    """Unzip an extension"""

    extzip = zipfile.ZipFile(filename)

    for fn in extzip.namelist():
        if fn.endswith("/") or fn.endswith("\\"):
            # skip directory entries
            continue

        # quick test for unusual filenames
        if fn.startswith("../") or "/../" in fn:
            raise Exception("bad file paths in zipfile '%s'" % fn)

        # determine extracted filename
        newfilename = os.path.join(outdir, fn)

        # ensure directory exists
        dirname = os.path.dirname(newfilename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        elif not os.path.isdir(dirname) or os.path.exists(newfilename):
            raise Exception("Cannot unzip.  Other files are in the way")

        # extract file
        out = open(newfilename, "wb")
        out.write(extzip.read(fn))
        out.flush()
        out.close()

        yield newfilename


class KeepNoteExtension (extension.Extension):
    """Extension that represents the application itself"""

    version = PROGRAM_VERSION
    key = "keepnote"
    name = "KeepNote"
    description = "The KeepNote application"
    visible = False

    def __init__(self, app):
        extension.Extension.__init__(self, app)

    def enable(self, enable):
        """This extension is always enabled"""
        extension.Extension.enable(self, True)
        return True

    def get_depends(self):
        """Application has no dependencies, returns []"""
        return []
