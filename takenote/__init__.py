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
    DEFAULT_WINDOW_SIZE, \
    DEFAULT_WINDOW_POS, \
    DEFAULT_VSASH_POS, \
    DEFAULT_HSASH_POS, \
    NoteBookError, \
    NoteBookNode, \
    NoteBookDir, \
    NoteBookPage, \
    NoteBook


#=============================================================================
# globals / constants

PROGRAM_NAME = "TakeNote"
PROGRAM_VERSION_MAJOR = 0
PROGRAM_VERSION_MINOR = 4
PROGRAM_VERSION_RELEASE = 0

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
    if p == "unix":
        if home is None:
            home = os.getenv("HOME")
        return os.path.join(home, "." + USER_PREF_DIR)
    elif p == "windows":
        appdata = os.getenv("APPDATA")
        return os.path.join(appdata, USER_PREF_DIR)
    else:
        raise Exception("unknown platform '%s'" % p)
        

def get_user_pref_file(home=None):
    """Returns the filename of the application preference file"""
    return os.path.join(get_user_pref_dir(home), USER_PREF_FILE)


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
    



#=============================================================================
# NoteBook data structures

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



class TakeNotePreferences (object):
    """Preference data structure for the TakeNote application"""
    
    def __init__(self):
        self.external_apps = []
        self._external_apps = []
        self._external_apps_lookup = {}
        self.view_mode = "vertical"
        self.default_notebook = ""

        # temp variables for parsing
        self._last_app_key = ""
        self._last_app_title = ""
        self._last_app_program = ""

    def read(self):
        if not os.path.exists(get_user_pref_file()):
            # write default
            try:
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
        for defapp in DEFAULT_EXTERNAL_APPS:
            if defapp.key not in self._external_apps_lookup:
                self.external_apps.append(defapp)
                self._external_apps_lookup[defapp.key] = defapp

        # place default apps first
        lookup = dict((x.key, i) for i, x in enumerate(DEFAULT_EXTERNAL_APPS))
        top = len(DEFAULT_EXTERNAL_APPS)
        self.external_apps.sort(key=lambda x: (lookup.get(x.key, top), x.key))
        
        
    def get_external_app(self, key):
        app = self._external_apps_lookup.get(key, None)
        if app == "":
            app = None
        return app

    
    def write(self):
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
        xmlo.Tag("view_mode",
            getobj=("view_mode", str),
            set=lambda s: s.view_mode),
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
        )
    ]))

