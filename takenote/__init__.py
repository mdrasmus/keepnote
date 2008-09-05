"""
    TakeNote
    Copyright Matt Rasmussen 2008

    Module for TakeNote
    
    Basic backend data structures for TakeNote and NoteBooks
"""


import xmlobject as xmlo

# python imports
import os, sys, shutil, time, re
import xml.dom.minidom as xmldom
import xml.dom

from takenote.notebook import \
    get_valid_filename, \
    get_unique_filename, \
    get_valid_unique_filename, \
    get_unique_filename_list, \
    get_str_timestamp, \
    DEFAULT_TIMESTAMP_FORMATS, \
    NoteBookError, \
    NoteBookNode, \
    NoteBookDir, \
    NoteBookPage, \
    NoteBook

from takenote.listening import Listeners


#=============================================================================
# globals / constants

PROGRAM_NAME = "TakeNote"
PROGRAM_VERSION_MAJOR = 0
PROGRAM_VERSION_MINOR = 4
PROGRAM_VERSION_RELEASE = 1

if PROGRAM_VERSION_RELEASE != 0:
    PROGRAM_VERSION_TEXT = "%d.%d.%d" % (PROGRAM_VERSION_MAJOR,
                                         PROGRAM_VERSION_MINOR,
                                         PROGRAM_VERSION_RELEASE)
else:
    PROGRAM_VERSION_TEXT = "%d.%d" % (PROGRAM_VERSION_MAJOR,
                                      PROGRAM_VERSION_MINOR)


BASEDIR = ""
IMAGE_DIR = "images"
PLATFORM = None

USER_PREF_DIR = "takenote"
USER_PREF_FILE = "takenote.xml"
USER_ERROR_LOG = "error-log.txt"


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

def get_user_pref_dir(home=None):
    """Returns the directory of the application preference file"""
    p = get_platform()
    if p == "unix" or p == "darwin":
        if home is None:
            home = os.getenv("HOME")
        return os.path.join(home, "." + USER_PREF_DIR)
    elif p == "windows":
        appdata = os.getenv("APPDATA")
        return os.path.join(appdata, USER_PREF_DIR)
    else:
        raise Exception("unknown platform '%s'" % p)


def get_user_documents(home=None):
    """Returns the directory of the user's documents"""
    p = get_platform()
    if p == "unix" or p == "darwin":
        if home is None:
            home = os.getenv("HOME")
        return home
    elif p == "windows":
        home = os.getenv("USERPROFILE")
        return os.path.join(home, "My Documents")
    else:
        return ""
        #raise Exception("unknown platform '%s'" % p)
    

def get_user_pref_file(home=None):
    """Returns the filename of the application preference file"""
    return os.path.join(get_user_pref_dir(home), USER_PREF_FILE)


def get_user_error_log(home=None):
    """Returns a file for the error log"""
    return os.path.join(get_user_pref_dir(home), USER_ERROR_LOG)


def init_user_pref(home=None):
    """Initializes the application preference file"""
    pref_dir = get_user_pref_dir(home)
    pref_file = get_user_pref_file(home)
    
    if not os.path.exists(pref_dir):
        os.mkdir(pref_dir)
    
    if not os.path.exists(pref_file):
        out = open(pref_file, "w")
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        out.write("<takenote>\n")
        out.write("</takenote>\n")
    



class TeeFileStream (file):
    """Create a file stream that forwards writes to multiple streams"""
    
    def __init__(self, streams, autoflush=False):
        self._streams = list(streams)
        self._autoflush = autoflush


    def write(self, data):
        for stream in self._streams:
            stream.write(data)
            if self._autoflush:
                stream.flush()

    def flush(self):
        for stream in self._streams:
            stream.flush()            


#=============================================================================
# Preference data structures

class ExternalApp (object):
    def __init__(self, key, title, prog, args=[]):
        self.key = key
        self.title = title
        self.prog = prog
        self.args = args


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
                "C:\Program Files\Internet Explorer\iexplore.exe"),
    ExternalApp("file_explorer", "File Explorer", "explorer.exe"),
    ExternalApp("text_editor", "Text Editor",
                "C:\Program Files\Windows NT\Accessories\wordpad.exe"),
    ExternalApp("image_editor", "Image Editor", "mspaint.exe"),
    ExternalApp("image_viewer", "Image Viewer",
                "C:\Program Files\Internet Explorer\iexplore.exe"),
    ExternalApp("screen_shot", "Screen Shot", "")
]



class TakeNotePreferences (object):
    """Preference data structure for the TakeNote application"""
    
    def __init__(self):
        self.external_apps = []
        self._external_apps = []
        self._external_apps_lookup = {}

        # window options
        self.window_size = DEFAULT_WINDOW_SIZE
        self.window_maximized = True
        self.vsash_pos = DEFAULT_VSASH_POS
        self.hsash_pos = DEFAULT_HSASH_POS        
        self.view_mode = DEFAULT_VIEW_MODE

        # autosave
        self.autosave = True
        self.autosave_time = DEFAULT_AUTOSAVE_TIME
        
        self.default_notebook = ""
        self.timestamp_formats = dict(DEFAULT_TIMESTAMP_FORMATS)
        self.spell_check = True

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


    def read(self):
        """Read preferences from file"""
        
        if not os.path.exists(get_user_pref_file()):
            # write default
            try:
                #self.set_defaults()
                self.write()
            except NoteBookError, e:
                raise NoteBookError("Cannot initialize preferences", e)

        # clear external apps vars
        self.external_apps = []
        self._external_apps_lookup = {}

        
        try:
            g_takenote_pref_parser.read(self, get_user_pref_file())
        except IOError, e:
            raise NoteBookError("Cannot read preferences", e)
        
        # make lookup
        for app in self.external_apps:
            self._external_apps_lookup[app.key] = app

        # add default programs
        if get_platform() == "windows":
            lst = DEFAULT_EXTERNAL_APPS_WINDOWS
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
            if not os.path.exists(get_user_pref_dir()):            
                os.mkdir(get_user_pref_dir())
        
            g_takenote_pref_parser.write(self, get_user_pref_file())
        except (IOError, OSError), e:
            raise NoteBookError("Cannot save preferences", e)


        

g_takenote_pref_parser = xmlo.XmlObject(
    xmlo.Tag("takenote", tags=[
        xmlo.Tag("default_notebook",
            getobj=("default_notebook", str),
            set=lambda s: s.default_notebook),

        # window sizing
        xmlo.Tag("view_mode",
            getobj=("view_mode", str),
            set=lambda s: s.view_mode),
        xmlo.Tag("window_size", 
            getobj=("window_size", lambda x: tuple(map(int,x.split(",")))),
            set=lambda s: "%d,%d" % s.window_size),
        xmlo.Tag("window_maximized",
            getobj=("window_maximized", lambda x: bool(int(x))),
            set=lambda s: "%d" % int(s.window_maximized)),
        xmlo.Tag("vsash_pos",
            getobj=("vsash_pos", int),
            set=lambda s: "%d" % s.vsash_pos),
        xmlo.Tag("hsash_pos",
            getobj=("hsash_pos", int),
            set=lambda s: "%d" % s.hsash_pos),

        # misc options
        xmlo.Tag("spell_check",
            getobj=("spell_check", lambda x: bool(int(x))),
            set=lambda s: "%d" % int(s.spell_check)),

        xmlo.Tag("autosave",
            getobj=("autosave", lambda x: bool(int(x))),
            set=lambda s: str(int(s.autosave))),
        xmlo.Tag("autosave_time",
            getobj=("autosave_time", int),
            set=lambda s: "%d" % s.autosave_time),

        # default paths
        xmlo.Tag("new_notebook_path",
            getobj=("new_notebook_path", str),
            set=lambda s: s.new_notebook_path),
        xmlo.Tag("archive_notebook_path",
            getobj=("archive_notebook_path", str),
            set=lambda s: s.new_notebook_path),
        xmlo.Tag("insert_image_path",
            getobj=("insert_image_path", str),
            set=lambda s: s.insert_image_path),
        xmlo.Tag("save_image_path",
            getobj=("save_image_path", str),
            set=lambda s: s.save_image_path),
        
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

