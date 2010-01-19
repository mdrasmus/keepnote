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
import imp
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
    NoteBookError, \
    get_unique_filename_list
from keepnote import timestamp
import keepnote.notebook as notebooklib
from keepnote import xdg
from keepnote import xmlobject as xmlo
from keepnote.listening import Listeners
from keepnote.util import compose
from keepnote import mswin
import keepnote.trans
from keepnote.trans import GETTEXT_DOMAIN
from keepnote import extension


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
PROGRAM_VERSION_RELEASE = 2
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

WEBSITE = u"http://rasm.ods.org/keepnote"
LICENSE_NAME = "GPL version 2"
COPYRIGHT = "Copyright Matt Rasmussen 2009."
TRANSLATOR_CREDITS = (
    "French: tb <thibaut.bethune@gmail.com>\n"
    "Turkish: Yuce Tekol <yucetekol@gmail.com>\n"
    "Spanish: Klemens Hackel <click3d at linuxmail (dot) org>\n")




BASEDIR = unicode(os.path.dirname(__file__))
IMAGE_DIR = u"images"
NODE_ICON_DIR = os.path.join(IMAGE_DIR, u"node_icons")
PLATFORM = None

USER_PREF_DIR = u"keepnote"
USER_PREF_FILE = u"keepnote.xml"
USER_LOCK_FILE = u"lockfile"
USER_ERROR_LOG = u"error-log.txt"
USER_EXTENSIONS_DIR = u"extensions"
USER_EXTENSIONS_DATA_DIR = u"extensions_data"



DEFAULT_WINDOW_SIZE = (800, 600)
DEFAULT_WINDOW_POS = (-1, -1)
DEFAULT_VSASH_POS = 200
DEFAULT_HSASH_POS = 200
DEFAULT_VIEW_MODE = "vertical"
DEFAULT_AUTOSAVE_TIME = 10 * 1000 # 10 sec (in msec)



#=============================================================================
# application resources

# TODO: cleanup, make get/set_basedir symmetrical

def get_basedir():
    return os.path.dirname(__file__)

def set_basedir(basedir):
    global BASEDIR
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


FS_ENCODING = sys.getfilesystemencoding()
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
    return unicode(text, "utf8")


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


def get_user_pref_dir(home=None):
    """Returns the directory of the application preference file"""
    
    p = get_platform()
    if p == "unix" or p == "darwin":
        if home is None:
            home = get_home()
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

    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)
    return os.path.join(pref_dir, USER_ERROR_LOG)


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


def log_error(error, tracebk=None, out=None):
    """Write an exception error to the error log"""
    
    if out is None:
        out = sys.stderr

    out.write("\n")
    traceback.print_exception(type(error), error, tracebk, file=out)


def log_message(message, out=None):
    """Write a message to the error log"""

    if out is None:
        out = sys.stderr
    out.write(message)



#=============================================================================
# Preference data structures

class ExternalApp (object):
    """Class represents the information needed for calling an external application"""

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
        self.timestamp_formats = dict(timestamp.DEFAULT_TIMESTAMP_FORMATS)
        self.spell_check = True
        self.image_size_snap = True
        self.image_size_snap_amount = 50
        self.use_systray = True
        self.skip_taskbar = False
        self.recent_notebooks = []

        self.language = ""

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
        extension.init_user_extensions(self._pref_dir)
                
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
            raise NoteBookError(_("Cannot save preferences"), e)


        

g_keepnote_pref_parser = xmlo.XmlObject(
    xmlo.Tag("keepnote", tags=[
        xmlo.Tag("id", attr=("id", None, None)),
        xmlo.Tag("language", attr=("language", None, None)),

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
        self._notebook_count = {}
        
        # set of associated extensions with application
        self._extensions = {}

        self.pref.changed.add(self.load_preferences)


    def init(self):
        """Initialize from preferences saved on disk"""
        
        # read preferences
        self.pref.read()
        self.set_lang()
        
        # scan extensions
        self.clear_extensions()
        self.scan_extensions_dir(get_system_extensions_dir())
        self.scan_extensions_dir(get_user_extensions_dir())

        # initialize all extensions
        self.init_extensions()


    def load_preferences(self):
        """Load information from preferences"""
        pass


    def save_preferneces(self):
        """TODO: not used yet"""
        pass

        #self._app.pref.write()

    def set_lang(self):                
        """Set the language based on preference"""

        keepnote.trans.set_lang(self.pref.language)


    #==================================
    # actions

    def open_notebook(self, filename, window=None):
        """Open notebook"""
        
        notebook = notebooklib.NoteBook()
        notebook.load(filename)
        return notebook

    def close_notebook(self, notebook):
        """Close notebook"""
        if notebook in self._notebook_count:
            # reduce ref count
            self._notebook_count[notebook] -= 1

            # close if refcount is zero
            if self._notebook_count[notebook] == 0:
                del self._notebook_count[notebook]

                for key, val in self._notebooks.iteritems():
                    if val == notebook:
                        del self._notebooks[key]
                        break

                notebook.close()


    def get_notebook(self, filename, window=None):
        """Returns a an opened notebook at filename"""

        filename = os.path.realpath(filename)
        if filename not in self._notebooks:
            notebook = self.open_notebook(filename, window)
            self._notebooks[filename] = notebook
            self._notebook_count[notebook] = 1
        else:
            notebook = self._notebooks[filename]
            self._notebook_count[notebook] +=1 

        return notebook


    def iter_notebooks(self):
        """Iterate through open notebooks"""
        
        return self._notebooks.itervalues()

    
    def run_external_app(self, app_key, filename, wait=False):
        """Runs a registered external application on a file"""

        app = self.pref.get_external_app(app_key)
        
        if app is None or app.prog == "":
            raise KeepNoteError(_("Must specify program to use in Helper Application"))

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
                raise Exception(_("You must specify a Screen Shot program in Application Options"))

            # create temp file
            f, imgfile = tempfile.mkstemp(".png", filename)
            os.close(f)

            proc = subprocess.Popen([screenshot.prog, imgfile])
            if proc.wait() != 0:
                raise OSError("Exited with error")

        if not os.path.exists(imgfile):
            # catch error if image is not created
            raise Exception(_("The screenshot program did not create the necessary image file '%s'") % imgfile)

        return imgfile  



    #================================
    # extensions


    def clear_extensions(self):

        # disable all enabled extension
        for ext in self.iter_extensions(enabled=True):
            ext.disable()

        # add default application extension
        self._extensions = {"keepnote": ("", KeepNoteExtension(self))}


    def scan_extensions_dir(self, extensions_dir):
        """Scan extensions directory and store references in application"""
        
        for filename in extension.iter_extensions(extensions_dir):
            self._extensions[os.path.basename(filename)] = (filename, None)
        
        
    def init_extensions(self):
        """Initialize all extensions"""
        
        # ensure all extensions are imported first
        for ext in self.iter_extensions():
            pass

        # enable those extensions that have their dependencies met
        for ext in self.iter_extensions():
            # enable extension
            try:
                if ext.key not in self.pref.disabled_extensions:
                    log_message(_("enabling extension '%s'\n") % ext.key)
                    enabled = ext.enable(True)

            except extension.DependencyError, e:

                log_message(_("  skipping extension '%s':\n") % ext.key)
                for dep in ext.get_depends():
                    if not self.dependency_satisfied(dep):
                        log_message(_("    failed dependency: %s\n") % repr(dep))

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
                ext = extension.import_extension(self, name, filename)
                self._extensions[name] = (filename, ext)
            except KeepNotePreferenceError, e:
                log_error(e, sys.exc_info()[2])
                
        return ext


    def get_extension_base_dir(self, extkey):
        """Get base directory of an extension"""
        return self._extensions[extkey][0]
    
    def get_extension_data_dir(self, extkey):
        """Get the data directory of an extension"""
        return os.path.join(get_user_extensions_data_dir(), extkey)

    def iter_extensions(self, enabled=False):
        """
        Iterate through all extensions

        If 'enabled' is True, then only enabled extensions are returned.
        """

        for name in self._extensions:
            ext = self.get_extension(name)
            if ext and (ext.is_enabled() or not enabled):
                yield ext


    def dependency_satisfied(self, dep):
        """Returns True if dependency 'dep' is satisfied"""

        ext  = self.get_extension(dep[0])
        return extension.dependency_satisfied(ext, dep)


    def dependencies_satisfied(self, depends):
        """Returns True if dependencies 'depend' are satisfied"""

        for dep in depends:
            if not extension.dependency_satisfied(self.get_extension(dep[0]), 
                                                  dep):
                return False
        return True


    def on_extension_enabled(self, ext, enabled):
        """Callback for extension enabled"""

        if enabled:
            if ext.key in self.pref.disabled_extensions:
                self.pref.disabled_extensions.remove(ext.key)
        else:
            if ext.key not in self.pref.disabled_extensions:
                self.pref.disabled_extensions.append(ext.key)
    



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

