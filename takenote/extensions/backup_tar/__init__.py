#
# TakeNote Extension 
# backup_tar
#
# Tar file notebook backup
#

import os, re, shutil, time
import tarfile

import takenote
from takenote.notebook import NoteBookError, get_valid_unique_filename
from takenote import notebook as notebooklib

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



class Extension (takenote.Extension):
    
    version = "1.0"
    name = "TAR Backup"
    description = "Backups a notebook to a gzip tar file (*.tar.gz)"


    def __init__(self, app):
        """Initialize extension"""
        
        takenote.Extension.__init__(self, app)
        self.app = app


    def on_new_window(self, window):
        """Initialize extension for a particular window"""

        insert_point = window.menubar_file_extensions
        menu = insert_point.get_parent()
        i = menu.get_children().index(insert_point)
        
        menu.insert(gtk.SeparatorMenuItem(), i+1)

        item = gtk.MenuItem("_Backup Notebook")
        item.connect("activate", lambda w: self.on_archive_notebook(window))
        menu.insert(item, i+2)

        item = gtk.MenuItem("_Restore Notebook")
        item.connect("activate", lambda w: self.on_restore_notebook(window))
        menu.insert(item, i+3)


    def on_archive_notebook(self, window):
        """Callback from gui for archiving a notebook"""

        if window.notebook is None:
            return

        dialog = gtk.FileChooserDialog("Backup Notebook", window, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Backup", gtk.RESPONSE_OK))


        filename = notebooklib.get_unique_filename(
            window.app.pref.archive_notebook_path,
            time.strftime(os.path.basename(window.notebook.get_path()) +
                          "-%Y-%m-%d"),
            ".tar.gz",
            ".")
        dialog.set_current_name(os.path.basename(filename))
        dialog.set_current_folder(window.app.pref.archive_notebook_path)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.tar.gz")
        file_filter.set_name("Archives (*.tar.gz)")
        dialog.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)

        response = dialog.run()

        window.app.pref.archive_notebook_path = dialog.get_current_folder()


        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            dialog.destroy()

            if "." not in filename:
                filename += ".tar.gz"

            window.set_status("Archiving...")
            self.archive_notebook(window, filename)

        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()


    def on_restore_notebook(self, window):
        """Callback from gui for restoring a notebook from an archive"""

        dialog = gtk.FileChooserDialog("Chose Archive To Restore", window, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Restore", gtk.RESPONSE_OK))
        dialog.set_current_folder(window.app.pref.archive_notebook_path)        


        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.tar.gz")
        file_filter.set_name("Archive (*.tar.gz)")
        dialog.add_filter(file_filter)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)

        response = dialog.run()

        window.app.pref.archive_notebook_path = dialog.get_current_folder()

        if response == gtk.RESPONSE_OK:
            archive_filename = dialog.get_filename()
            dialog.destroy()

        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return


        # choose new notebook name
        dialog = gtk.FileChooserDialog("Choose New Notebook Name", window, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "New", gtk.RESPONSE_OK))
        dialog.set_current_folder(window.app.pref.archive_notebook_path)

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

        window.app.pref.archive_notebook_path = os.path.dirname(dialog.get_current_folder())


        if response == gtk.RESPONSE_OK:
            notebook_filename = dialog.get_filename()
            dialog.destroy()

            window.set_status("Restoring...")
            self.restore_notebook(window, archive_filename, notebook_filename)

        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()



    def archive_notebook(self, window, filename):
        """Archive a notebook"""

        if window.notebook is None:
            return


        def progress(percent, filename):
            pass
            #print percent, filename

        try:
            archive_notebook(window.notebook, filename, progress)

        except NoteBookError, e:
            window.set_status("")
            window.error("Error while archiving notebook:\n%s" % e.msg, e)
            return

        except Exception, e:
            window.set_status("")
            window.error("unknown error", e)
            return

        window.set_status("Notebook archived")


    def restore_notebook(self, window, archive_filename, notebook_filename):

        # make sure current notebook is closed
        window.close_notebook()

        try:
            restore_notebook(archive_filename, notebook_filename)
            window.set_status("Notebook restored")

        except NoteBookError, e:
            window.set_status("")
            window.error("Error restoring notebook:\n%s" % e.msg, e)
            return

        except Exception, e:
            window.set_status("")
            window.error("unknown error", e)
            return

        # open new notebook
        window.open_notebook(notebook_filename)




def archive_notebook(notebook, filename, progress=lambda p, f: None):
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
        archive = tarfile.open(filename, "w:gz")
        path = notebook.get_path()

        # first count # of files
        nfiles = 0
        for root, dirs, files in os.walk(path):
            nfiles += len(files)

        nfiles2 = [0]
        def walk(path, arcname):
            # add to archive
            archive.add(path, arcname, False)

            # report progresss
            if os.path.isfile(path):
                nfiles2[0] += 1
                progress(nfiles2[0] / float(nfiles), path)

            # recurse
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if not os.path.islink(f):
                        walk(os.path.join(path, f),
                             os.path.join(arcname, f))
        walk(path, os.path.basename(path))

        archive.close()
    except Exception, e:
        raise NoteBookError("Error while archiving notebook", e)


def restore_notebook(filename, path, rename=True):
    """
    Restores a archived notebook

    filename -- filename of archive
    path     -- name of new notebook
    rename   -- if True, path contains notebook name, otherwise path is
                basedir of new notebook
    """

    if path == "":
        raise NoteBookError("Must specify a path for restoring notebook")

    # remove trailing "/"
    path = re.sub("/+$", "", path)

    tar = tarfile.open(filename, "r:gz")

    # create new dirctory, if needed
    if rename:
        if not os.path.exists(path):
            tmppath = get_valid_unique_filename(os.path.dirname(path),
                                                os.path.basename(path+"-tmp"))
        else:
            raise NoteBookError("Notebook path already exists")

        try:
            # extract notebook
            if hasattr(tar, "extractall"):
                tar.extractall(tmppath)
            else:
                # fallback code for python2.4
                for member in tar.getmembers():
                    tar.extract(member, tmppath)

            files = os.listdir(tmppath)
            # assert len(files) = 1
            extracted_path = os.path.join(tmppath, files[0])

            # move extracted files to proper place
            shutil.move(extracted_path, path)
            os.rmdir(tmppath)
        except Exception, e:
            raise NoteBookError("File writing error while extracting notebook", e)

    else:
        try:
            tar.extractall(path)
        except Exception, e:
            raise NoteBookError("File writing error while extracting notebook", e)


