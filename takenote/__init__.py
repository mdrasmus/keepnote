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
# globals

BASEDIR = ""
IMAGE_DIR = "images"
PLATFORM = None

USER_PREF_DIR = "takenote"
USER_PREF_FILE = "takenote.xml"

g_pixbufs = {}


#=============================================================================
# GUI resources

def set_basedir(basedir):
    global BASEDIR
    BASEDIR = basedir

def get_resource(*path_list):
    return os.path.join(BASEDIR, *path_list)

def get_image(filename):

    # NOTE: I want to make sure gtk is not a requirement for __init__
    # TODO: maybe I will make a base module for gtk interaction
    import gtk
    
    img = gtk.Image()
    img.set_from_file(filename)    
    return img


def get_pixbuf(filename):
    # NOTE: I want to make sure gtk is not a requirement for __init__
    # TODO: maybe I will make a base module for gtk interaction
    import gtk
    
    if filename in g_pixbufs:
        return g_pixbufs[filename]
    else:

        # raises GError
        pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
        g_pixbufs[filename] = pixbuf
        return pixbuf
    

def get_resource_image(*path_list):
    return get_image(get_resource(IMAGE_DIR, *path_list))

def get_resource_pixbuf(*path_list):
    # raises GError
    return get_pixbuf(get_resource(IMAGE_DIR, *path_list))
        




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

class TakeNotePreferences (object):
    """Preference data structure for the TakeNote application"""
    
    def __init__(self):
        self.external_apps = {}
        self.view_mode = "vertical" # "horizontal"
        self.default_notebook = ""

        # temp variables for parsing
        self._last_app_name = ""
        self._last_app_program = ""

    def read(self):
        if not os.path.exists(get_user_pref_file()):
            # write default
            try:
                self.write()
            except NoteBookError, e:
                raise NoteBookError("Cannot initialize preferences", e)
        
        try:
            g_takenote_pref_parser.read(self, get_user_pref_file())
        except IOError, e:
            raise NoteBookError("Cannot read preferences", e)
            
    
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
                before=lambda (s,i): setattr(s, "_last_app_name", "") or
                                     setattr(s, "_last_app_program", ""),
                after=lambda (s,i): s.external_apps.__setitem__(
                    s._last_app_name,
                    s._last_app_program),
                tags=[
                    xmlo.Tag("name",
                        get=lambda (s,i),x: s.__setattr__("_last_app_name", x),
                        set=lambda (s,i): s.external_apps.keys()[i]),
                    xmlo.Tag("program",                             
                        get=lambda (s,i),x: s.__setattr__("_last_app_program",x),
                        set=lambda (s,i): s.external_apps.values()[i])]
           )]
        )
    ]))

