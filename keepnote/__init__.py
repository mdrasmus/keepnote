"""
    KeepNote
    Copyright Matt Rasmussen 2008

    Module for KeepNote
    
    Basic backend data structures for KeepNote and NoteBooks
"""


# python imports
import os, sys, shutil, time, re, imp, subprocess
import xml.dom.minidom as xmldom
import xml.dom

from keepnote.notebook import \
    DEFAULT_TIMESTAMP_FORMATS, \
    NoteBookError, \
    get_unique_filename_list

from keepnote import xdg
from keepnote import xmlobject as xmlo
from keepnote.listening import Listeners
from keepnote import safefile


#=============================================================================
# modules needed by builtin extensions
# these are imported here, so that py2exe can auto-discover them
import tarfile

#=============================================================================
# globals / constants

PROGRAM_NAME = "KeepNote"
PROGRAM_VERSION_MAJOR = 0
PROGRAM_VERSION_MINOR = 5
PROGRAM_VERSION_RELEASE = 2

if PROGRAM_VERSION_RELEASE != 0:
    PROGRAM_VERSION_TEXT = "%d.%d.%d" % (PROGRAM_VERSION_MAJOR,
                                         PROGRAM_VERSION_MINOR,
                                         PROGRAM_VERSION_RELEASE)
else:
    PROGRAM_VERSION_TEXT = "%d.%d" % (PROGRAM_VERSION_MAJOR,
                                      PROGRAM_VERSION_MINOR)

WEBSITE = "http://rasm.ods.org/keepnote"


BASEDIR = ""
IMAGE_DIR = "images"
PLATFORM = None

USER_PREF_DIR = "takenote"
USER_PREF_FILE = "takenote.xml"
USER_ERROR_LOG = "error-log.txt"
USER_EXTENSIONS_DIR = "extensions"
XDG_USER_EXTENSIONS_DIR = "takenote/extensions"


DEFAULT_WINDOW_SIZE = (800, 600)
DEFAULT_WINDOW_POS = (-1, -1)
DEFAULT_VSASH_POS = 200
DEFAULT_HSASH_POS = 200
DEFAULT_VIEW_MODE = "vertical"
DEFAULT_AUTOSAVE_TIME = 10 * 1000 # 10 sec (in msec)


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

def get_platform():
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
            home = os.getenv("HOME")
            if home is None:
                raise EnvError("HOME environment variable must be specified")
        old_dir = os.path.join(home, "." + USER_PREF_DIR)

        return not os.path.exists(old_dir)
    
    else:
        return False
    

def get_user_pref_dir(home=None):
    """Returns the directory of the application preference file"""
    
    p = get_platform()
    if p == "unix" or p == "darwin":
        
        if home is None:
            home = os.getenv("HOME")
            if home is None:
                raise EnvError("HOME environment variable must be specified")
        old_dir = os.path.join(home, "." + USER_PREF_DIR)

        if os.path.exists(old_dir):
            return old_dir
        else:
            return xdg.get_config_file(USER_PREF_DIR, default=True)

    elif p == "windows":
        appdata = os.getenv("APPDATA")
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
    return os.path.join(BASEDIR, "extensions")


def get_user_documents(home=None):
    """Returns the directory of the user's documents"""
    p = get_platform()
    if p == "unix" or p == "darwin":
        if home is None:
            home = os.getenv("HOME")
        return home
    
    elif p == "windows":
        home = os.getenv("USERPROFILE")

        # TODO can I find a way to find "My Documents"?
        return os.path.join(home, "My Documents")
    
    else:
        return ""
        #raise Exception("unknown platform '%s'" % p)
    

def get_user_pref_file(pref_dir=None, home=None):
    """Returns the filename of the application preference file"""
    if pref_dir is None:
        pref_dir = get_user_pref_dir(home)
    return os.path.join(pref_dir, USER_PREF_FILE)


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

#=============================================================================
# utilities

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
    ExternalApp("web_browser", "Web Browser", ""),
    ExternalApp("file_explorer", "File Explorer", ""),
    ExternalApp("text_editor", "Text Editor", ""),
    ExternalApp("image_editor", "Image Editor", ""),
    ExternalApp("image_viewer", "Image Viewer", ""),
    ExternalApp("screen_shot", "Screen Shot", "")
]


DEFAULT_EXTERNAL_APPS_WINDOWS = [
    ExternalApp("web_browser", "Web Browser",
                "C:\\Program Files\\Internet Explorer\\iexplore.exe"),
    ExternalApp("file_explorer", "File Explorer", "explorer.exe"),
    ExternalApp("text_editor", "Text Editor",
                "C:\Program Files\\Windows NT\\Accessories\\wordpad.exe"),
    ExternalApp("image_editor", "Image Editor", "mspaint.exe"),
    ExternalApp("image_viewer", "Image Viewer",
                "C:\\Program Files\\Internet Explorer\\iexplore.exe"),
    ExternalApp("screen_shot", "Screen Shot", "")
]


DEFAULT_EXTERNAL_APPS_LINUX = [
    ExternalApp("web_browser", "Web Browser", ""),
    ExternalApp("file_explorer", "File Explorer", ""),
    ExternalApp("text_editor", "Text Editor", ""),
    ExternalApp("image_editor", "Image Editor", ""),
    ExternalApp("image_viewer", "Image Viewer", "display"),
    ExternalApp("screen_shot", "Screen Shot", "import")
]


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

        # window presentation options
        self.window_size = DEFAULT_WINDOW_SIZE
        self.window_maximized = True
        self.vsash_pos = DEFAULT_VSASH_POS
        self.hsash_pos = DEFAULT_HSASH_POS        
        self.view_mode = DEFAULT_VIEW_MODE

        self.last_treeview_node_path = []
        
        self.treeview_lines = True
        self.listview_rules = True
        self.use_stock_icons = False
        

        # autosave
        self.autosave = True
        self.autosave_time = DEFAULT_AUTOSAVE_TIME
        
        self.default_notebook = ""
        self.timestamp_formats = dict(DEFAULT_TIMESTAMP_FORMATS)
        self.spell_check = True
        self.image_size_snap = True
        self.image_size_snap_amount = 50
        self.use_systray = True
        self.skip_taskbar = False

        # dialog chooser paths
        self.new_notebook_path = get_user_documents()
        self.archive_notebook_path = get_user_documents()
        self.insert_image_path = get_user_documents()
        self.save_image_path = get_user_documents()
        
        # temp variables for parsing
        self._last_app_key = ""
        self._last_app_title = ""
        self._last_app_program = ""
        self._last_timestamp_name = ""
        self._last_timestamp_format = ""

        # listener
        self.changed = Listeners()


    def get_pref_dir(self):
        """Returns preference directory"""
        return self._pref_dir
    

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

        
        # make lookup
        for app in self.external_apps:
            self._external_apps_lookup[app.key] = app

        # add default programs
        if get_platform() == "windows":
            lst = DEFAULT_EXTERNAL_APPS_WINDOWS
        elif get_platform() == "unix":
            lst = DEFAULT_EXTERNAL_APPS_LINUX
        else:
            lst = DEFAULT_EXTERNAL_APPS
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
        xmlo.Tag("default_notebook",
                 attr=("default_notebook", None, None)),

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

        #xmlo.Tag("last_treeview_node_path",
        #         getobj=("last_treeview_node_path",
        #                 lambda x: x.split("/")),
        #         set=lambda s: "/".join(s.last_tree_view_node_path)),
        
        xmlo.Tag("treeview_lines",
                 attr=("treeview_lines", xmlo.str2bool, xmlo.bool2str)),
        xmlo.Tag("listview_rules",
                 attr=("listview_rules", xmlo.str2bool, xmlo.bool2str)),
        xmlo.Tag("use_stock_icons",
                 attr=("use_stock_icons", xmlo.str2bool, xmlo.bool2str)),

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
        
        xmlo.Tag("external_apps", tags=[
           xmlo.TagMany("app",
                iterfunc=lambda s: range(len(s.external_apps)),
                before=lambda (s,i): setattr(s, "_last_app_key", "") or
                                     setattr(s, "_last_app_title", "") or 
                                     setattr(s, "_last_app_program", ""),
                after=lambda (s,i):
                    s.external_apps.append(ExternalApp(
                        s._last_app_key,
                        s._last_app_title,
                        s._last_app_program)),
                tags=[
                    xmlo.Tag("title",
                        get=lambda (s,i),x: setattr(s, "_last_app_title", x),
                        set=lambda (s,i): s.external_apps[i].title),
                    xmlo.Tag("name",
                        get=lambda (s,i),x: setattr(s, "_last_app_key", x),
                        set=lambda (s,i): s.external_apps[i].key),
                    xmlo.Tag("program",                             
                        get=lambda (s,i),x: setattr(s, "_last_app_program", x),
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

    
    def __init__(self, basedir=""):
        set_basedir(basedir)        
        self.basedir = basedir
        
        # load application preferences
        self.pref = KeepNotePreferences()
        self.pref.read()

        self.window = None
        
        # get extensions list
        self._extensions = {}
        self.scan_extensions_dir(get_system_extensions_dir())
        self.scan_extensions_dir(get_user_extensions_dir())
        self.init_extensions()

        

    def show_main_window(self):
        """show main window"""
        from keepnote.gui import main_window
        self.window = main_window.KeepNoteWindow(self)
        self.init_extensions_window()
        
        self.window.show_all()

        
    def open_notebook(self, filename):
        """Open notebook in window"""
        if self.window is None:
            self.show_main_window()
        self.window.open_notebook(filename)


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

        # execute command
        try:
            proc = subprocess.Popen(cmd)
        except OSError, e:
            raise KeepNoteError(
                ("Error occurred while opening file with %s.\n\n" 
                 "program: %s\n\n"
                 "file: %s\n\n"
                 "error: %s")
                % (app.title, app.prog, filename, str(e)), e)

        # wait for process to return
        # TODO: perform waiting in gtk loop
        # NOTE: I do not wait for any program yet
        if wait:
            return proc.wait()


    def open_webpage(self, url):
        """View a node with an external web browser"""

        if url:
            self.run_external_app("web_browser", url)
        
            

    #================================
    # extensions


    def scan_extensions_dir(self, extensions_dir):
        """Scan extensions directory"""
        
        for filename in iter_extensions(extensions_dir):
            self._extensions[os.path.basename(filename)] = (filename, None)

    def init_extensions(self):
        errors = []
        
        for name in self._extensions:
            try:
                ext = self.get_extension(name)
            except KeepNotePreferenceError, e:
                errors.append(e)

        if len(errors) > 0:
            raise KeepNotePreferenceError("\n".join(str(e) for e in errors))


    def init_extensions_window(self):
        errors = []
        
        for name in self._extensions:
            try:
                ext = self.get_extension(name)
                ext.on_new_window(self.window)
                
            except KeepNotePreferenceError,e :
                errors.append(e)
    
            
    def get_extension(self, name):
        """Get an extension module by name"""
        
        try:
            filename, ext = self._extensions[name]        
        except KeyError:
            raise KeepNotePreferenceError("unknown extension '%s'" % name)

        # load if first use
        if ext is None:
            filename2 = os.path.join(filename, "__init__.py")
            infile = open(filename2)
            name = os.path.basename(filename)

            try:
                mod = imp.load_module(name, infile, filename2,
                                      (".py", "rb", imp.PY_SOURCE))
                ext = mod.Extension(self)
                self._extensions[name] = (filename, ext)
                
            except Exception, e:
                infile.close()
                raise KeepNotePreferenceError("cannot load extension '%s'" %
                                              filename, e)            
            infile.close()
                
        return ext
        

class Extension (object):
    """KeepNote Extension"""

    version = "1.0"
    name = "untitled"
    description = "extension"


    def __init__(self, app):
        pass

    def on_new_window(self, window):
        pass

    
