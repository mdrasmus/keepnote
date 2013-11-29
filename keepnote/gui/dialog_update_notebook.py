"""

    KeepNote
    Update notebook dialog

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

# python imports
import sys
import shutil

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk.glade

# keepnote imports
import keepnote
from keepnote import unicode_gtk
from keepnote.gui import dialog_wait
from keepnote import tasklib
from keepnote.notebook import update
from keepnote import notebook as notebooklib
from keepnote.gui import get_resource, FileChooserDialog

_ = keepnote.translate


MESSAGE_TEXT = _("This notebook has format version %d and must be updated to "
                 "version %d before opening.")


class UpdateNoteBookDialog (object):
    """Updates a notebook"""

    def __init__(self, app, main_window):
        self.main_window = main_window
        self.app = app

    def show(self, notebook_filename, version=None, task=None):
        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "update_notebook_dialog",
                                 keepnote.GETTEXT_DOMAIN)
        self.dialog = self.xml.get_widget("update_notebook_dialog")
        self.xml.signal_autoconnect(self)
        self.dialog.connect("close", lambda w:
                            self.dialog.response(gtk.RESPONSE_CANCEL))
        self.dialog.set_transient_for(self.main_window)

        self.text = self.xml.get_widget("update_message_label")
        self.saved = self.xml.get_widget("save_backup_check")

        if version is None:
            version = notebooklib.get_notebook_version(notebook_filename)

        self.text.set_text(MESSAGE_TEXT %
                           (version,
                            notebooklib.NOTEBOOK_FORMAT_VERSION))

        ret = False
        response = self.dialog.run()

        if response == gtk.RESPONSE_OK:

            # do backup
            if self.saved.get_active():
                if not self.backup(notebook_filename):
                    self.dialog.destroy()
                    return False

            self.dialog.destroy()

            # do update
            def func(task):
                update.update_notebook(
                    notebook_filename,
                    notebooklib.NOTEBOOK_FORMAT_VERSION)

            # TODO: reuse existing task
            task = tasklib.Task(func)
            dialog2 = dialog_wait.WaitDialog(self.main_window)
            dialog2.show(_("Updating Notebook"),
                         _("Updating notebook..."),
                         task, cancel=False)

            ret = not task.aborted()
            ty, err, tb = task.exc_info()
            if err:
                self.main_window.error(_("Error while updating."), err, tb)
                ret = False
        else:
            self.dialog.destroy()

        if ret:
            self.app.message(_("Notebook updated successfully"),
                             _("Notebook Update Complete"),
                             self.main_window)

        return ret

    def backup(self, notebook_filename):

        dialog = FileChooserDialog(
            _("Choose Backup Notebook Name"),
            self.main_window,
            action=gtk.FILE_CHOOSER_ACTION_SAVE,  # CREATE_FOLDER,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Backup"), gtk.RESPONSE_OK),
            app=self.app,
            persistent_path="new_notebook_path")

        response = dialog.run()

        new_filename = dialog.get_filename()
        dialog.destroy()

        if response == gtk.RESPONSE_OK and new_filename:
            new_filename = unicode_gtk(new_filename)

            def func(task):
                try:
                    shutil.copytree(notebook_filename, new_filename)
                except Exception, e:
                    print >>sys.stderr, e
                    print >>sys.stderr, "'%s' '%s'" % (notebook_filename,
                                                       new_filename)
                    raise
            task = tasklib.Task(func)
            dialog2 = dialog_wait.WaitDialog(self.dialog)
            dialog2.show(_("Backing Up Notebook"),
                         _("Backing up old notebook..."),
                         task, cancel=False)

            # handle errors
            if task.aborted():
                ty, err, tb = task.exc_info()
                if err:
                    self.main_window.error(_("Error occurred during backup."),
                                           err, tb)
                else:
                    self.main_window.error(_("Backup canceled."))
                return False

        return True
