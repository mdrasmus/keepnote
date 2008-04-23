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



BASEDIR = ""
def get_resource(*path_list):
    return os.path.join(BASEDIR, *path_list)

PLATFORM = None

USER_PREF_DIR = "takenote"
USER_PREF_FILE = "takenote.xml"


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
            xmlo.Tag("file_explorer", 
                get=lambda s,x: s.external_apps.__setitem__(
                    "file_explorer", x),
                set=lambda s: s.external_apps.get("file_explorer", "")),
            xmlo.Tag("web_browser", 
                get=lambda s,x: s.external_apps.__setitem__(
                    "web_browser", x),
                set=lambda s: s.external_apps.get("web_browser", "")),
            xmlo.Tag("image_editor", 
                get=lambda s,x: s.external_apps.__setitem__(
                    "image_editor", x),
                set=lambda s: s.external_apps.get("image_editor", "")),
            xmlo.Tag("text_editor", 
                get=lambda s,x: s.external_apps.__setitem__(
                    "text_editor", x),
                set=lambda s: s.external_apps.get("text_editor", "")),
                
            ])
        ]))
        

