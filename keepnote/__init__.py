"""
    KeepNote
    Module for KeepNote
    
    Basic backend data structures for KeepNote and NoteBooks
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



# python imports
import gettext
import imp
import locale
import os
import shutil
import sys
import time
import re
import subprocess
import tempfile
import traceback

# keepnote imports
from keepnote.notebook import \
    DEFAULT_TIMESTAMP_FORMATS, \
    NoteBookError, \
    get_unique_filename_list
import keepnote.notebook as notebooklib
from keepnote import xdg
from keepnote import xmlobject as xmlo
from keepnote.listening import Listeners
from keepnote import safefile
from keepnote.util import compose
from keepnote import mswin

# import screenshot so that py2exe discovers it
try:
    import mswin.screenshot
except ImportError:
    pass


#=============================================================================
# modules needed by builtin extensions
# these are imported here, so that py2exe can auto-discover them
from keepnote import tarfile
import xml.dom.minidom
import xml.sax.saxutils

#=============================================================================
# globals / constants

PROGRAM_NAME = u"KeepNote"
PROGRAM_VERSION_MAJOR = 0
PROGRAM_VERSION_MINOR = 6
PROGRAM_VERSION_RELEASE = 1
PROGRAN_VERSION = (PROGRAM_VERSION_MAJOR,
                   PROGRAM_VERSION_MINOR,
                   PROGRAM_VERSION_RELEASE)

if PROGRAM_VERSION_RELEASE != 0:
    PROGRAM_VERSION_TEXT = "%d.%d.%d" % (PROGRAM_VERSION_MAJOR,
                                         PROGRAM_VERSION_MINOR,
                                         PROGRAM_VERSION_RELEASE)
else:
    PROGRAM_VERSION_TEXT = "%d.%d" % (PROGRAM_VERSION_MAJOR,
                                      PROGRAM_VERSION_MINOR)

WEBSITE = u"http://rasm.ods.org/keepnote"


BASEDIR = unicode(os.path.dirname(__file__))
IMAGE_DIR = u"images"
NODE_ICON_DIR = os.path.join(IMAGE_DIR, u"node_icons")
PLATFORM = None

# backward compatiable files
USER_PREF_DIR_OLD = u"takenote"
USER_PREF_FILE_OLD = u"takenote.xml"
XDG_USER_EXTENSIONS_DIR_OLD = u"takenote/extensions"

USER_PREF_DIR = u"takenote"
USER_PREF_FILE = u"takenote.xml"
USER_LOCK_FILE = u"lockfile"
USER_ERROR_LOG = u"error-log.txt"
USER_EXTENSIONS_DIR = u"extensions"
XDG_USER_EXTENSIONS_DIR = u"takenote/extensions"


DEFAULT_WINDOW_SIZE = (800, 600)
DEFAULT_WINDOW_POS = (-1, -1)
DEFAULT_VSASH_POS = 200
DEFAULT_HSASH_POS = 200
DEFAULT_VIEW_MODE = "vertical"
DEFAULT_AUTOSAVE_TIME = 10 * 1000 # 10 sec (in msec)

GETTEXT_DOMAIN = 'keepnote'

#=============================================================================
# application resources

def get_basedir():
    return os.path.dirname(__file__)

def set_basedir(basedir):
    global BASEDIR
    BASEDIR = basedir

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

def unicode_fs(text):
    """Converts a string from the filesystem to unicode"""

    if text is None:
        return None

    if not isinstance(text, unicode):
        if encoding == FS_ENCODING:
            return unicode(text, sys.getfilesystemencoding())
    
    return text

def unicode_gtk(text):
    """Converts a string from gtk (utf8) to unicode"""
    return unicode(text, "utf8")


#=============================================================================
# locale functions


def set_locale():
    locale.setlocale(locale.LC_ALL, '')
    gettext.bindtextdomain(GETTEXT_DOMAIN, get_locale_dir())
    gettext.textdomain(GETTEXT_DOMAIN)


def translate(message):
    return gettext.gettext(message)

'''
#Translation stuff

#Get the local directory since we are not installing anything
self.local_path = os.path.realpath(os.path.dirname(sys.argv[0]))
# Init the list of languages to support
langs = []
#Check the default locale
lc, encoding = locale.getdefaultlocale()
if (lc):
	#If we have a default, it's the first in the list
	langs = [lc]
# Now lets get all of the supported languages on the system
language = os.environ.get('LANGUAGE', None)
if (language):
	"""langage comes back something like en_CA:en_US:en_GB:en
	on linuxy systems, on Win32 it's nothing, so we need to
	split it up into a list"""
	langs += language.split(":")
"""Now add on to the back of the list the translations that we
know that we have, our defaults"""
langs += ["en_CA", "en_US"]

"""Now langs is a list of all of the languages that we are going
to try to use.  First we check the default, then what the system
told us, and finally the 'known' list"""

gettext.bindtextdomain(APP_NAME, self.local_path)
gettext.textdomain(APP_NAME)
# Get the language to use
self.lang = gettext.translation(APP_NAME, self.local_path
	, languages=langs, fallback = True)
"""Install the language, map _() (which we marked our
strings to translate with) to self.lang.gettext() which will
translate them."""
_ = self.lang.gettext
'''



#=============================================================================
# filenaming scheme


def use_xdg(home=None):
    """
    Returns True if configuration is stored in XDG

    Only returns True if platform is unix and old config $HOME/.keepnote 
    does not exist.
    """

    if get_platform() == "unix":
        if home is None:
            home = ensure_unicode(os.getenv("HOME"), FS_ENCODING)
            if home is None:
                raise EnvError("HOME environment variable must be specified")
        old_dir = os.path.join(home, "." + USER_PREF_DIR)

        return not os.path.exists(old_dir)
    
    else:
        return False


def get_locale_dir():
    """Returns KeepNote's locale directory"""
    #return os.path.join(BASEDIR, u"..", u"locale")
    return get_resource(u"rc", u"locale")


#def get_nonxdg_user_pref_dir(home=None):
    

def get_user_pref_dir(home=None):
    """Returns the directory of the application preference file"""
    
    p = get_platform()
    if p == "unix" or p == "darwin":
        
        if home is None:
            home = ensure_unicode(os.getenv(u"HOME"), FS_ENCODING)
                                  
            if home is None:
                raise EnvError("HOME environment variable must be specified")
        old_dir = os.path.join(home, u"." + USER_PREF_DIR)

        if os.path.exists(old_dir):
            return old_dir
        else:
            return xdg.get_config_file(USER_PREF_DIR, default=True)

    elif p == "windows":
        appdata = ensure_unicode(os.getenv(u"APPDATA"), FS_ENCODING)
        if appdata is None:
            raise EnvError("APPDATA environment variable must be specified")
        return os.path.join(appdata, USER_PREF_DIR)

    else:
        raise Exception("unknown platform '%s'" % p)


def get_user_extensions_dir(pref_dir=None, home=None):
    """Returns user extensions directory"""

    if not use_xdg():
        if pref_dir is None:
            pref_dir = get_user_pref_dir(home)
        return os.path.join(pref_dir, USER_EXTENSIONS_DIR)
    else:
        return xdg.get_data_file(XDG_USER_EXTENSIONS_DIR, default=True)


def get_system_extensions_dir():
    """Returns system-wdie extensions directory"""
    return os.path.join(BASEDIR, u"extensions")


def get_user_documents(home=None):
    """Returns the directory of the user's documents"""
    p = get_platform()
    if p == "unix" or p == "darwin":
        if home is None:
            home = ensure_unicode(os.getenv(u"HOME"), FS_ENCODING)
        return home
    
    elif p == "windows":
        return mswin.get_my_documents()
    
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

    if use_xdg():
         return xdg.get_data_file(os.path.join(USER_PREF_DIR, USER_ERROR_LOG),
                                  default=True)
    else:
        if pref_dir is None:
            pref_dir = get_user_pref_dir(home)
        return os.path.join(pref_dir, USER_ERROR_LOG)


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
        out.write("<takenote>\n")
        out.write("</takenote>\n")
        out.close()

    # init error log
    init_error_log(pref_dir)

    # init user extensions
    init_user_extensions(pref_dir)


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


def log_error(error, tracebk=None, out=sys.stderr):
    """Write an exception error to the error log"""
    
    out.write("\n")
    traceback.print_exception(type(error), error, tracebk, file=out)


#=============================================================================
# extension functions


def init_user_extensions(pref_dir=None, home=None):
    """Ensure users extensions are initialized
       Install defaults if needed"""

    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)
    extensions_dir = get_user_extensions_dir(pref_dir)

    if not os.path.exists(extensions_dir):
        # make dir
        os.makedirs(extensions_dir, 0700)


def iter_extensions(extensions_dir):
    """Iterate through the extensions in directory"""

    for filename in os.listdir(extensions_dir):
        yield os.path.join(extensions_dir, filename)



def import_extension(app, name, filename):
    
    filename2 = os.path.join(filename, "__init__.py")

    try:
        infile = open(filename2)
        #name = os.path.basename(filename)
    except Exception, e:
        raise KeepNotePreferenceError("cannot load extension '%s'" %
                                      filename, e)

    try:
        mod = imp.load_module(name, infile, filename2,
                              (".py", "rb", imp.PY_SOURCE))
        ext = mod.Extension(app)
        ext.key = name
        return ext
                
    except Exception, e:
        infile.close()
        raise KeepNotePreferenceError("cannot load extension '%s'" %
                                      filename, e)            
    infile.close()


#=============================================================================
# Preference data structures

class ExternalApp (object):
    def __init__(self, key, title, prog, args=[]):
        self.key = key
        self.title = title
        self.prog = prog
        self.args = args


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
        files = os.environ.get("PROGRAMFILES", u"C:\\Program Files")

        return [
            ExternalApp("file_launcher", "File Launcher", "explorer.exe"),
            ExternalApp("web_browser", "Web Browser",
                        files + u"\\Internet Explorer\\iexplore.exe"),
            ExternalApp("file_explorer", "File Explorer", "explorer.exe"),
            ExternalApp("text_editor", "Text Editor",
                        files + u"\\Windows NT\\Accessories\\wordpad.exe"),
            ExternalApp("image_editor", "Image Editor", "mspaint.exe"),
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
        


# TODO: maybe merge with app class?

class KeepNotePreferences (object):
    """Preference data structure for the KeepNote application"""
    
    def __init__(self, pref_dir=None):

        if pref_dir is None:
            self._pref_dir = get_user_pref_dir()
        else:
            self._pref_dir = pref_dir

        # external apps
        self.external_apps = []
        self._external_apps = []
        self._external_apps_lookup = {}

        self.id = None

        # extensions
        self.disabled_extensions = []

        # window presentation options
        self.window_size = DEFAULT_WINDOW_SIZE
        self.window_maximized = True
        self.vsash_pos = DEFAULT_VSASH_POS
        self.hsash_pos = DEFAULT_HSASH_POS
        self.view_mode = DEFAULT_VIEW_MODE
        
        # look and feel
        self.treeview_lines = True
        self.listview_rules = True
        self.use_stock_icons = False
        self.use_minitoolbar = False

        # autosave
        self.autosave = True
        self.autosave_time = DEFAULT_AUTOSAVE_TIME
        
        self.default_notebook = ""
        self.use_last_notebook = True
        self.timestamp_formats = dict(DEFAULT_TIMESTAMP_FORMATS)
        self.spell_check = True
        self.image_size_snap = True
        self.image_size_snap_amount = 50
        self.use_systray = True
        self.skip_taskbar = False
        self.recent_notebooks = []

        # dialog chooser paths
        docs = get_user_documents()
        self.new_notebook_path = docs
        self.archive_notebook_path = docs
        self.insert_image_path = docs
        self.save_image_path = docs
        self.attach_file_path = docs
        
        

        # temp variables for parsing
        self._last_timestamp_name = ""
        self._last_timestamp_format = ""

        # listener
        self.changed = Listeners()
        self.changed.add(self._on_changed)


    def get_pref_dir(self):
        """Returns preference directory"""
        return self._pref_dir
    

    def _on_changed(self):
        """Listener for preference changes"""
        self.write()
        


    def read(self):
        """Read preferences from file"""

        # ensure preference file exists
        if not os.path.exists(get_user_pref_file(self._pref_dir)):
            # write default
            try:
                init_user_pref_dir(self._pref_dir)
                self.write()
            except NoteBookError, e:
                raise NoteBookError("Cannot initialize preferences", e)

        # clear external apps vars
        self.external_apps = []
        self._external_apps_lookup = {}

        # read xml preference file
        try:
            g_keepnote_pref_parser.read(self,
                                        get_user_pref_file(self._pref_dir))
        except IOError, e:
            raise NoteBookError("Cannot read preferences", e)


        # setup id
        if self.id is None:
            self.id = str(uuid.uuid4())
        
        # make lookup
        for app in self.external_apps:
            self._external_apps_lookup[app.key] = app

        # add default programs
        lst = get_external_app_defaults()
        for defapp in lst:
            if defapp.key not in self._external_apps_lookup:
                self.external_apps.append(defapp)
                self._external_apps_lookup[defapp.key] = defapp

        # place default apps first
        lookup = dict((x.key, i) for i, x in enumerate(DEFAULT_EXTERNAL_APPS))
        top = len(DEFAULT_EXTERNAL_APPS)
        self.external_apps.sort(key=lambda x: (lookup.get(x.key, top), x.key))


        # initialize user extensions directory
        user_extensions_dir = get_user_extensions_dir(self._pref_dir)
        if not os.path.exists(user_extensions_dir):
            init_user_extensions(self._pref_dir)
        
        
        # notify listeners
        self.changed.notify()


        
    def get_external_app(self, key):
        """Return an external application by its key name"""
        app = self._external_apps_lookup.get(key, None)
        if app == "":
            app = None
        return app

    
    def write(self):
        """Write preferences to file"""
        
        try:
            if not os.path.exists(self._pref_dir):
                init_user_pref_dir(self._pref_dir)
        
            g_keepnote_pref_parser.write(self,
                                         get_user_pref_file(self._pref_dir))
        except (IOError, OSError), e:
            raise NoteBookError("Cannot save preferences", e)


        

g_keepnote_pref_parser = xmlo.XmlObject(
    xmlo.Tag("takenote", tags=[
        xmlo.Tag("id", attr=("id", None, None)),
        xmlo.Tag("default_notebook",
                 attr=("default_notebook", None, None)),
        xmlo.Tag("use_last_notebook",
                 attr=("use_last_notebook", xmlo.str2bool, xmlo.bool2str)),

        # window presentation options
        xmlo.Tag("view_mode",
                 attr=("view_mode", None, None)),
        xmlo.Tag("window_size",
                 attr=("window_size",
                       lambda x: tuple(map(int, x.split(","))),
                       lambda x: "%d,%d" % x)),
        xmlo.Tag("window_maximized",
                 attr=("window_maximized", xmlo.str2bool, xmlo.bool2str)), 
        xmlo.Tag("vsash_pos",
                 attr=("vsash_pos", int, compose(str, int))),
        xmlo.Tag("hsash_pos",
                 attr=("hsash_pos", int, compose(str, int))),

        
        xmlo.Tag("treeview_lines",
                 attr=("treeview_lines", xmlo.str2bool, xmlo.bool2str)),
        xmlo.Tag("listview_rules",
                 attr=("listview_rules", xmlo.str2bool, xmlo.bool2str)),
        xmlo.Tag("use_stock_icons",
                 attr=("use_stock_icons", xmlo.str2bool, xmlo.bool2str)),
        xmlo.Tag("use_minitoolbar",
                 attr=("use_minitoolbar", xmlo.str2bool, xmlo.bool2str)),


        # image resize
        xmlo.Tag("image_size_snap",
                 attr=("image_size_snap", xmlo.str2bool, xmlo.bool2str)),
        xmlo.Tag("image_size_snap_amount",
                 attr=("image_size_snap_amount", int, compose(str, int))),

        xmlo.Tag("use_systray",
                 attr=("use_systray", xmlo.str2bool, xmlo.bool2str)),
        xmlo.Tag("skip_taskbar",
                 attr=("skip_taskbar", xmlo.str2bool, xmlo.bool2str)),
                 
        # misc options
        xmlo.Tag("spell_check",
                 attr=("spell_check", xmlo.str2bool, xmlo.bool2str)),

        xmlo.Tag("autosave",
                 attr=("autosave", xmlo.str2bool, xmlo.bool2str)),
        xmlo.Tag("autosave_time",
                 attr=("autosave_time", int, compose(str, int))),
                 
        # default paths
        xmlo.Tag("new_notebook_path",
                 attr=("new_notebook_path", None, None)),        
        xmlo.Tag("archive_notebook_path",
                 attr=("archive_notebook_path", None, None)),
        xmlo.Tag("insert_image_path",
                 attr=("insert_image_path", None, None)),
        xmlo.Tag("save_image_path",
                 attr=("save_image_path", None, None)),
        xmlo.Tag("attach_file_path",
                 attr=("attach_file_path", None, None)),
        

        # recent notebooks
        xmlo.Tag("recent_notebooks", tags=[
           xmlo.TagMany("notebook",
                iterfunc=lambda s: range(len(s.recent_notebooks)),
                get=lambda (s, i), x: s.recent_notebooks.append(x),
                set=lambda (s, i): s.recent_notebooks[i]
                        )
           ]),

        # disabled extensions
        xmlo.Tag("extensions", tags=[
            xmlo.Tag("disabled", tags=[
                xmlo.TagMany("extension",
                iterfunc=lambda s: range(len(s.disabled_extensions)),
                get=lambda (s, i), x: s.disabled_extensions.append(x),
                set=lambda (s, i): s.disabled_extensions[i]
                        )
                ]),
            ]),


        xmlo.Tag("external_apps", tags=[

           xmlo.TagMany("app",
                iterfunc=lambda s: range(len(s.external_apps)),
                before=lambda (s,i):
                        s.external_apps.append(ExternalApp("", "", "")),
                tags=[
                    xmlo.Tag("title",
                        get=lambda (s,i),x:
                             setattr(s.external_apps[i], "title", x),
                        set=lambda (s,i): s.external_apps[i].title),
                    xmlo.Tag("name",
                        get=lambda (s,i),x:
                             setattr(s.external_apps[i], "key", x),
                        set=lambda (s,i): s.external_apps[i].key),
                    xmlo.Tag("program",                             
                        get=lambda (s,i),x:
                             setattr(s.external_apps[i], "prog", x),
                        set=lambda (s,i): s.external_apps[i].prog)]
           )]
          
        ),
        xmlo.Tag("timestamp_formats", tags=[
            xmlo.TagMany("timestamp_format",
                iterfunc=lambda s: range(len(s.timestamp_formats)),
                before=lambda (s,i): setattr(s, "_last_timestamp_name", "") or
                                     setattr(s, "_last_timestamp_format", ""),
                after=lambda (s,i):
                    s.timestamp_formats.__setitem__(
                        s._last_timestamp_name,
                        s._last_timestamp_format),
                tags=[
                    xmlo.Tag("name",
                        get=lambda (s,i),x: setattr(s, "_last_timestamp_name", x),
                        set=lambda (s,i): s.timestamp_formats.keys()[i]),
                    xmlo.Tag("format",
                        get=lambda (s,i),x: setattr(s, "_last_timestamp_format", x),
                        set=lambda (s,i): s.timestamp_formats.values()[i])
                    ]
            )]
        )
    ]))




#=============================================================================
# Application class

        
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



class KeepNote (object):
    """KeepNote application class"""

    
    def __init__(self, basedir=None):

        # base directory of keepnote library
        if basedir is not None:
            set_basedir(basedir)
        self._basedir = BASEDIR
        
        # load application preferences
        self.pref = KeepNotePreferences()

        # list of application notebooks
        self._notebooks = {}
        
        # set of associated extensions with application
        self._extensions = {}

        # read preferences
        self.pref.read()

        # scan extensions
        self.scan_extensions_dir(get_system_extensions_dir())
        self.scan_extensions_dir(get_user_extensions_dir())

        # initialize all extensions
        self.init_extensions()
        

    #==================================
    # actions

    def open_notebook(self, filename, window=None):
        """Open notebook"""
        
        notebook = notebooklib.NoteBook()
        notebook.load(filename)
        return notebook


    def run_external_app(self, app_key, filename, wait=False):
        """Runs a registered external application on a file"""

        app = self.pref.get_external_app(app_key)
        
        if app is None:
            raise KeepNoteError("Must specify program to use in Application Options")         

        # build command arguments
        cmd = [app.prog] + app.args
        if "%s" not in cmd:
            cmd.append(filename)
        else:
            for i in xrange(len(cmd)):
                if cmd[i] == "%s":
                    cmd[i] = filename
        
        # create proper encoding
        cmd = map(lambda x: unicode(x), cmd)
        if get_platform() == "windows":
            cmd = [x.encode('mbcs') for x in cmd]
        
        # execute command
        try:
            proc = subprocess.Popen(cmd)
        except OSError, e:
            raise KeepNoteError(
                (u"Error occurred while opening file with %s.\n\n" 
                 u"program: %s\n\n"
                 u"file: %s\n\n"
                 u"error: %s")
                % (app.title, app.prog, filename, unicode(e)), e)

        # wait for process to return
        # TODO: perform waiting in gtk loop
        # NOTE: I do not wait for any program yet
        if wait:
            return proc.wait()


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
            screenshot = self.pref.get_external_app("screen_shot")
            if screenshot is None or screenshot.prog == "":
                raise Exception("You must specify a Screen Shot program in Application Options")

            # create temp file
            f, imgfile = tempfile.mkstemp(".png", filename)
            os.close(f)

            proc = subprocess.Popen([screenshot.prog, imgfile])
            if proc.wait() != 0:
                raise OSError("Exited with error")

        if not os.path.exists(imgfile):
            # catch error if image is not created
            raise Exception("The screenshot program did not create the necessary image file '%s'" % imgfile)

        return imgfile  



    #================================
    # extensions


    def scan_extensions_dir(self, extensions_dir):
        """Scan extensions directory and store references in application"""
        
        for filename in iter_extensions(extensions_dir):
            self._extensions[os.path.basename(filename)] = (filename, None)
        
        
    def init_extensions(self):
        """Initialize all extensions"""
        
        for ext in self.iter_extensions():
            # enable extension
            try:
                if ext.key not in self.pref.disabled_extensions:
                    ext.enable(True)
            except Exception, e:
                log_error(e, sys.exc_info()[2])
    
            
    def get_extension(self, name):
        """Get an extension module by name"""
        
        # return None if extension name is unknown
        if name not in self._extensions:
            return None

        # get extension information
        filename, ext = self._extensions[name]        

        # load if first use
        if ext is None:
            try:
                ext = import_extension(self, name, filename)
                self._extensions[name] = (filename, ext)
            except KeepNotePreferenceError, e:
                log_error(e, sys.exc_info()[2])
                
        return ext


    def iter_extensions(self):
        """Iterate through all extensions"""

        for name in self._extensions:
            ext = self.get_extension(name)
            if ext:
                yield ext


    def on_extension_enabled(self, ext, enabled):
        """Callback for extension enabled"""

        if enabled:
            if ext.key in self.pref.disabled_extensions:
                self.pref.disabled_extensions.remove(ext.key)
        else:
            if ext.key not in self.pref.disabled_extensions:
                self.pref.disabled_extensions.append(ext.key)
    


class Extension (object):
    """KeepNote Extension"""

    version = (1, 0)
    key = ""
    name = "untitled"
    description = "base extension"


    def __init__(self, app):
        
        self._app = app
        self._enabled = False
        self._windows = set()
        self._uis = set()


    def enable(self, enable):
        self._enabled = enable

        if enable:
            for window in self._windows:
                if window not in self._uis:
                    self.on_add_ui(window)
                    self._uis.add(window)
        else:
            for window in self._uis:
                self.on_remove_ui(window)
            self._uis.clear()

        # call callback for app
        self._app.on_extension_enabled(self, enable)

        # call callback for enable event
        self.on_enabled(enable)

    def is_enabled(self):
        return self._enabled

    def on_enabled(self, enabled):
        """Callback for when extension is enabled/disabled"""
        pass

    
    def on_new_window(self, window):
        """Initialize extension for a particular window"""

        if self._enabled:
            self.on_add_ui(window)
            self._uis.add(window)
        self._windows.add(window)


    def on_close_window(self, window):
        """Callback for when window is closed"""
     
        if window in self._windows:
            if window in self._uis:
                self.on_remove_ui(window)
                self._uis.remove(window)
            self._windows.remove(window)


    def on_add_ui(self, window):
        pass

    def on_remove_ui(self, window):
        pass
