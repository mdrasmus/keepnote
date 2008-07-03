"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for TakeNote Application
"""



# python imports
import sys, os, tempfile, re, subprocess, shlex, shutil

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# takenote imports
import takenote
from takenote import get_resource
from takenote.notebook import \
     NoteBookError, \
     NoteBookDir, \
     NoteBookPage, \
     NoteBookTrash


# globals
_g_pixbufs = {}
_g_node_icons = {}

def quote_filename(filename):
    if " " in filename:
        filename = filename.replace("\\", "\\\\")
        filename = filename.replace('"', '\"')
        filename = '"%s"' % filename
    return filename


def get_pixbuf(filename):
    """
    Get pixbuf from a filename

    Cache pixbuf for later use
    """
    
    if filename in _g_pixbufs:
        return _g_pixbufs[filename]
    else:
        # may raise GError
        pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
        _g_pixbufs[filename] = pixbuf
        return pixbuf
    

def get_resource_image(*path_list):
    """Returns gtk.Image from resource path"""
    
    filename = get_resource(takenote.IMAGE_DIR, *path_list)
    img = gtk.Image()
    img.set_from_file(filename)
    return img

def get_resource_pixbuf(*path_list):
    """Returns cached pixbuf from resource path"""
    # raises GError
    return get_pixbuf(get_resource(takenote.IMAGE_DIR, *path_list))
        
def get_node_icon_filenames(node):
    """Returns NoteBookNode icon filename from resource path"""
    
    if isinstance(node, NoteBookTrash):
        return (get_resource(takenote.IMAGE_DIR, "trash.png"),
                get_resource(takenote.IMAGE_DIR, "trash.png"))
    
    elif isinstance(node, NoteBookDir):
        return (get_resource(takenote.IMAGE_DIR, "folder.png"),
                get_resource(takenote.IMAGE_DIR, "folder-open.png"))
    
    elif isinstance(node, NoteBookPage):
        filename = get_resource(takenote.IMAGE_DIR, "note.png")
        return (filename, filename)

    else:
        raise Exception("Unknown node type")



def get_node_icon(node, expand=False):
    """Returns cached pixbuf of NoteBookNode icon from resource path"""
    
    if node in _g_node_icons:
        return _g_node_icons[node][int(expand)]
    else:
        filenames = get_node_icon_filenames(node)
        pixbufs  = (get_pixbuf(filenames[0]),
                    get_pixbuf(filenames[1]))
        _g_node_icons[node] = pixbufs
        return pixbufs[int(expand)]

        
        
class TakeNoteError (StandardError):
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



#=============================================================================
# Application class
# NOTE: I could place this in an application module takenote.gui.app


class TakeNote (object):
    """TakeNote application class"""

    
    def __init__(self, basedir=""):
        takenote.set_basedir(basedir)
        
        self.basedir = basedir
        
        # load application preferences
        self.pref = takenote.TakeNotePreferences()
        self.pref.read()

        self.window = None

    def show_main_window(self):
        """show main window"""
        from takenote.gui import main_window
        self.window = main_window.TakeNoteWindow(self)
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
            raise TakeNoteError("Must specify program to use in Application Options")         

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
            raise TakeNoteError(
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


