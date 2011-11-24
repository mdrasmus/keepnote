"""
    KeepNote Extension 
    backup_tar

    Tar file notebook backup
"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
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

import gettext
import os
import re
import shutil
import sys
import time

#_ = gettext.gettext

import keepnote
from keepnote import unicode_gtk
from keepnote.notebook import NoteBookError, get_unique_filename
from keepnote import notebook as notebooklib
from keepnote import tasklib
from keepnote import tarfile
from keepnote.gui import extension, FileChooserDialog

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



class Extension (extension.Extension):

    def __init__(self, app):
        """Initialize extension"""
        
        extension.Extension.__init__(self, app)
        self.app = app


    def get_depends(self):
        return [("keepnote", ">=", (0, 7, 1))]


    def on_add_ui(self, window):
        """Initialize extension for a particular window"""

        # add menu options
        self.add_action(window, "Backup Notebook", "_Backup Notebook...",
                        lambda w: self.on_archive_notebook(
                window, window.get_notebook()))
        self.add_action(window, "Restore Notebook", "R_estore Notebook...",
                        lambda w: self.on_restore_notebook(window))
        
        # add menu items
        self.add_ui(window,
            """
            <ui>
            <menubar name="main_menu_bar">
               <menu action="File">
                  <placeholder name="Extensions">
                     <menuitem action="Backup Notebook"/>
                     <menuitem action="Restore Notebook"/>
                  </placeholder>
               </menu>
            </menubar>
            </ui>
            """)


    def on_archive_notebook(self, window, notebook):
        """Callback from gui for archiving a notebook"""

        if notebook is None:
            return

        dialog = FileChooserDialog(
            "Backup Notebook", window, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Backup", gtk.RESPONSE_OK),
            app=self.app,
            persistent_path="archive_notebook_path")

        path = self.app.get_default_path("archive_notebook_path")
        if os.path.exists(path):
            filename = notebooklib.get_unique_filename(
                path,
                os.path.basename(notebook.get_path()) +
                time.strftime("-%Y-%m-%d"), ".tar.gz", ".")
        else: 
            filename = os.path.basename(notebook.get_path()) + \
                time.strftime("-%Y-%m-%d") + u".tar.gz"
        
        dialog.set_current_name(os.path.basename(filename))


        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.tar.gz")
        file_filter.set_name("Archives (*.tar.gz)")
        dialog.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)

        response = dialog.run()

        if response == gtk.RESPONSE_OK and dialog.get_filename():
            filename = unicode_gtk(dialog.get_filename())
            dialog.destroy()

            if u"." not in filename:
                filename += u".tar.gz"

            window.set_status("Archiving...")
            return self.archive_notebook(notebook, filename, window)
            

        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return False
            


    def on_restore_notebook(self, window):
        """Callback from gui for restoring a notebook from an archive"""

        dialog = FileChooserDialog(
            "Chose Archive To Restore", window, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Restore", gtk.RESPONSE_OK),
            app=self.app,
            persistent_path="archive_notebook_path")

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.tar.gz")
        file_filter.set_name("Archive (*.tar.gz)")
        dialog.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)

        response = dialog.run()
        

        if response == gtk.RESPONSE_OK and dialog.get_filename():
            archive_filename = unicode_gtk(dialog.get_filename())
            dialog.destroy()

        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return


        # choose new notebook name
        dialog = FileChooserDialog(
            "Choose New Notebook Name", window, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "New", gtk.RESPONSE_OK),
            app=self.app,
            persistent_path="new_notebook_path")

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.nbk")
        file_filter.set_name("Notebook (*.nbk)")
        dialog.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.tar.gz")
        file_filter.set_name("Archives (*.tar.gz)")
        dialog.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)

        response = dialog.run()

        if response == gtk.RESPONSE_OK and dialog.get_filename():
            notebook_filename = unicode_gtk(dialog.get_filename())
            dialog.destroy()

            window.set_status("Restoring...")
            self.restore_notebook(archive_filename,
                                  notebook_filename, window)

        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()



    def archive_notebook(self, notebook, filename, window=None):
        """Archive a notebook"""

        if notebook is None:
            return


        task = tasklib.Task(lambda task:
            archive_notebook(notebook, filename, task))


        if window:

            window.wait_dialog("Creating archive '%s'..." %
                               os.path.basename(filename),
                               "Beginning archive...",
                               task)

            # check exceptions
            try:
                ty, error, tracebk = task.exc_info()
                if error:
                    raise error
                window.set_status("Notebook archived")
                return True

            except NoteBookError, e:
                window.set_status("")
                window.error("Error while archiving notebook:\n%s" % e.msg, e,
                             tracebk)
                return False

            except Exception, e:
                window.set_status("")
                window.error("unknown error", e, tracebk)
                return False

        else:
            
            archive_notebook(notebook, filename, None)

        
    def restore_notebook(self, archive_filename, notebook_filename,
                         window=None):
        """Restore notebook"""

        if window:

            # make sure current notebook is closed
            window.close_notebook()

            task = tasklib.Task(lambda task:
                restore_notebook(archive_filename, notebook_filename, True, task))

            window.wait_dialog("Restoring notebook from '%s'..." %
                               os.path.basename(archive_filename),
                               "Opening archive...",
                               task)

            # check exceptions
            try:
                ty, error, tracebk = task.exc_info()
                if error:
                    raise error
                window.set_status("Notebook restored")

            except NoteBookError, e:
                window.set_status("")
                window.error("Error restoring notebook:\n%s" % e.msg, e, tracebk)
                return

            except Exception, e:
                window.set_status("")
                window.error("unknown error", e, tracebk)
                return

            # open new notebook
            window.open_notebook(notebook_filename)

        else:
            restore_notebook(archive_filename, notebook_filename, True, None)


def truncate_filename(filename, maxsize=100):
    if len(filename) > maxsize:
        filename = "..." + filename[-(maxsize-3):]
    return filename


def archive_notebook(notebook, filename, task=None):
    """Archive notebook as *.tar.gz

       filename -- filename of archive to create
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


    # perform archiving
    archive = tarfile.open(filename, "w:gz", format=tarfile.PAX_FORMAT)
    path = notebook.get_path()

    # first count # of files
    nfiles = 0
    for root, dirs, files in os.walk(path):
        nfiles += len(files)

    task.set_message(("text", "Archiving %d files..." % nfiles))

    nfiles2 = [0]
    def walk(path, arcname):
        # add to archive
        archive.add(path, arcname, False)

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
                    archive.close()
                    os.remove(filename)
                    raise NoteBookError("Backup canceled")

                if not os.path.islink(f):
                    walk(os.path.join(path, f),
                         os.path.join(arcname, f))

    walk(path, os.path.basename(path))

    task.set_message(("text", "Closing archive..."))
    task.set_message(("detail", ""))

    archive.close()

    if task:
        task.finish()




def restore_notebook(filename, path, rename, task=None):
    """
    Restores a archived notebook

    filename -- filename of archive
    path     -- name of new notebook
    rename   -- if True, path contains notebook name, otherwise path is
                basedir of new notebook
    """

    if task is None:
        # create dummy task if needed
        task = tasklib.Task()


    if path == "":
        raise NoteBookError("Must specify a path for restoring notebook")

    # remove trailing "/"
    path = re.sub("/+$", "", path)

    tar = tarfile.open(filename, "r:gz", format=tarfile.PAX_FORMAT)


    # create new dirctory, if needed
    if rename:
        if not os.path.exists(path):
            tmppath = get_unique_filename(os.path.dirname(path),
                                          os.path.basename(path+"-tmp"))
        else:
            raise NoteBookError("Notebook path already exists")

        try:
            # extract notebook
            members = list(tar.getmembers())

            if task:
                task.set_message(("text", "Restoring %d files..." %
                                  len(members)))

            for i, member in enumerate(members):
                # FIX: tarfile does not seem to keep unicode and str straight
                # make sure member.name is unicode
                if 'path' in member.pax_headers:
                    member.name = member.pax_headers['path']

                if task:
                    if task.aborted():
                        raise NoteBookError("Restore canceled")
                    task.set_message(("detail", truncate_filename(member.name)))
                    task.set_percent(i / float(len(members)))
                tar.extract(member, tmppath)

            files = os.listdir(tmppath)
            # assert len(files) = 1
            extracted_path = os.path.join(tmppath, files[0])
            
            # move extracted files to proper place
            if task:
                task.set_message(("text", "Finishing restore..."))
                shutil.move(extracted_path, path)
                os.rmdir(tmppath)


        except NoteBookError, e:
            raise e
        
        except Exception, e:
            raise NoteBookError("File writing error while extracting notebook", e)

    else:
        try:
            if task:
                task.set_message(("text", "Restoring archive..."))
            tar.extractall(path)
        except Exception, e:
            raise NoteBookError("File writing error while extracting notebook", e)

    task.finish()


#=============================================================================


def archive_notebook_zip(notebook, filename, task=None):
    """Archive notebook as *.tar.gz

       filename -- filename of archive to create
       progress -- callback function that takes arguments
                   (percent, filename)
    """

    if os.path.exists(filename):
        raise NoteBookError("File '%s' already exists" % filename)

    # make sure all modifications are saved first
    try:
        notebook.save()
    except Exception, e:
        raise NoteBookError("Could not save notebook before archiving", e)

    # perform archiving
    try:
        #archive = tarfile.open(filename, "w:gz")
        archive = zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED, True)
        path = notebook.get_path()

        # first count # of files
        nfiles = 0
        for root, dirs, files in os.walk(path):
            nfiles += len(files)

        nfiles2 = [0]
        abort = [False]
        def walk(path, arcname):
            # add to archive
            #archive.add(path, arcname, False)
            if os.path.isfile(path):
                archive.write(path, arcname)

            # report progresss
            if os.path.isfile(path):
                nfiles2[0] += 1
                if task:
                    task.set_message(path)
                    task.set_percent(nfiles2[0] / float(nfiles))


            # recurse
            if os.path.isdir(path):
                for f in os.listdir(path):

                    # abort archive
                    if not task.is_running():
                        abort[0] = True
                        return
                    
                    if not os.path.islink(f):
                        walk(os.path.join(path, f),
                             os.path.join(arcname, f))
                        
        walk(path, os.path.basename(path))

        archive.close()

        if abort[0]:
            os.remove(filename)
        elif task:
            task.finish()
            
        
    except Exception, e:
        raise NoteBookError("Error while archiving notebook", e)
