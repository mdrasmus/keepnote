"""

    KeepNote
    General Wait Dialog

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
import time

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk.glade
import gobject

# keepnote imports
import keepnote
from keepnote import get_resource


class WaitDialog (object):
    """General dialog for background tasks"""

    def __init__(self, parent_window):
        self.parent_window = parent_window
        self._task = None

    def show(self, title, message, task, cancel=True):
        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "wait_dialog", keepnote.GETTEXT_DOMAIN)
        self.dialog = self.xml.get_widget("wait_dialog")
        self.xml.signal_autoconnect(self)
        self.dialog.connect("close", self._on_close)
        self.dialog.set_transient_for(self.parent_window)
        self.text = self.xml.get_widget("wait_text_label")
        self.progressbar = self.xml.get_widget("wait_progressbar")

        self.dialog.set_title(title)
        self.text.set_text(message)
        self._task = task
        self._task.change_event.add(self._on_task_update)

        cancel_button = self.xml.get_widget("cancel_button")
        cancel_button.set_sensitive(cancel)

        self.dialog.show()
        self._task.run()
        self._on_idle()
        self.dialog.run()
        self._task.join()

        self._task.change_event.remove(self._on_task_update)

    def _on_idle(self):
        """Idle thread"""
        lasttime = [time.time()]
        pulse_rate = 0.5  # seconds per sweep
        update_rate = 100

        def gui_update():

            # close dialog if task is stopped
            if self._task.is_stopped():
                self.dialog.destroy()
                # do not repeat this timeout function
                return False

            # update progress bar
            percent = self._task.get_percent()
            if percent is None:
                t = time.time()
                timestep = t - lasttime[0]
                lasttime[0] = t
                step = max(min(timestep / pulse_rate, .1), .001)
                self.progressbar.set_pulse_step(step)
                self.progressbar.pulse()
            else:
                self.progressbar.set_fraction(percent)

            # filter for messages we process
            messages = filter(lambda x: isinstance(x, tuple) and len(x) == 2,
                              self._task.get_messages())
            texts = filter(lambda (a, b): a == "text", messages)
            details = filter(lambda (a, b): a == "detail", messages)

            # update text
            if len(texts) > 0:
                self.text.set_text(texts[-1][1])
            if len(details) > 0:
                self.progressbar.set_text(details[-1][1])

            # repeat this timeout function
            return True

        gobject.timeout_add(update_rate, gui_update)

    def _on_task_update(self):
        pass

    def _on_close(self, window):
        self._task.stop()

    def on_cancel_button_clicked(self, button):
        """Attempt to stop the task"""
        self.text.set_text("Canceling...")
        self._task.stop()
