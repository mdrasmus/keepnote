"""

    KeepNote
    Graphical User Interface for KeepNote Application

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
import os
import sys

_ = gettext.gettext


# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# keepnote imports
import keepnote





import keepnote
from keepnote.notebook import NoteBookError, get_valid_unique_filename
from keepnote import notebook as notebooklib
from keepnote import tasklib
from keepnote import tarfile

# pygtk imports
try:
    import pygtk
    pygtk.require('2.0')
    from gtk import gdk
    import gtk.glade
    import gobject
except ImportError:
    # do not fail on gtk import error,
    # extension should be usable for non-graphical uses
    pass



class Extension (keepnote.Extension):
    
    version = "1.0"
    name = "Export HTML"
    description = "Exports a notebook to HTML format"


    def __init__(self, app):
        """Initialize extension"""
        
        keepnote.Extension.__init__(self, app)
        self.app = app


    def on_new_window(self, window):
        """Initialize extension for a particular window"""

        # add menu options

        window.actiongroup.add_actions([
            ("Export HTML", None, "_HTML...",
             "", None,
             lambda w: self.on_export_notebook(window,
                                               window.get_notebook())),
            ])
        
        window.uimanager.add_ui_from_string(
            """
            <ui>
            <menubar name="main_menu_bar">
               <menu action="File">
                  <menu action="Export">
                     <menuitem action="Export HTML"/>
                  </menu>
               </menu>
            </menubar>
            </ui>
            """)


    def on_export_notebook(self, window, notebook):
        """Callback from gui for exporting a notebook"""
        
        dialog = gtk.FileChooserDialog("Export Notebook", window, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Backup", gtk.RESPONSE_OK))


        filename = notebooklib.get_unique_filename(
            self.app.pref.archive_notebook_path,
            time.strftime(os.path.basename(window.notebook.get_path()) +
                          "-%Y-%m-%d"),
            "",
            ".")
        dialog.set_current_name(os.path.basename(filename))
        dialog.set_current_folder(self.app.pref.archive_notebook_path)

        #file_filter = gtk.FileFilter()
        #file_filter.add_pattern("*.tar.gz")
        #file_filter.set_name("Archives (*.tar.gz)")
        #dialog.add_filter(file_filter)

        #file_filter = gtk.FileFilter()
        #file_filter.add_pattern("*")
        #file_filter.set_name("All files (*.*)")
        #dialog.add_filter(file_filter)

        response = dialog.run()

        self.app.pref.archive_notebook_path = dialog.get_current_folder()
        self.app.pref.changed.notify()


        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            dialog.destroy()

            self.export_notebook(notebook, filename, window=window)


    def export_notebook(self, notebook, filename, window=None):
        
        if notebook is None:
            return

        task = tasklib.Task(lambda task:
            export_notebook(notebook, filename, task))

        window.wait_dialog("Exporting to '%s'..." %
                           os.path.basename(filename),
                           "Beginning export...",
                           task)

        # check exceptions
        try:
            ty, error, tracebk = task.exc_info()
            if error:
                raise error
            window.set_status("Notebook exported")
            return True

        except NoteBookError, e:
            window.set_status("")
            window.error("Error while exporting notebook:\n%s" % e.msg, e,
                         tracebk)
            return False

        except Exception, e:
            window.set_status("")
            window.error("unknown error", e, tracebk)
            return False


def export_notebook(notebook, filename, task):
    """Export notebook to HTML

       filename -- filename of export to create
    """

    if task is None:
        # create dummy task if needed
        task = tasklib.Task()


    if os.path.exists(filename):
        raise NoteBookError("File '%s' already exists" % filename)

    # make sure all modifications are saved first
    try:
        notebook.save()
    except Exception, e:
        raise NoteBookError("Could not save notebook before archiving", e)


    # perform export
    try:
        # first count # of files
        nfiles = 0
        for root, dirs, files in os.walk(path):
            nfiles += len(files)

        task.set_message(("text", "Exporting %d files..." % nfiles))

        nfiles2 = [0]
        def walk(path, arcname):
            # add to export
            #archive.add(path, arcname, False)
            
            # report progresss
            if os.path.isfile(path):
                nfiles2[0] += 1
                if task:
                    task.set_message(("detail", truncate_filename(path)))
                    task.set_percent(nfiles2[0] / float(nfiles))


            # recurse
            if os.path.isdir(path):
                for f in os.listdir(path):

                    # abort archive
                    if task.aborted():
                        #archive.close()
                        #os.remove(filename)
                        raise NoteBookError("Backup canceled")
                    
                    if not os.path.islink(f):
                        walk(os.path.join(path, f),
                             os.path.join(arcname, f))
                        
        walk(path, os.path.basename(path))

        task.set_message(("text", "Closing export..."))
        task.set_message(("detail", ""))

        #archive.close()

        if task:
            task.finish()
            
        
    except Exception, e:
        raise e






