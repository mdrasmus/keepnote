"""

    TakeNote
    General Wait Dialog

"""

# python imports
import os, sys, threading, time, traceback


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk.glade
import gobject

# takenote imports
import takenote
from takenote import get_resource
from takenote import tasklib    
    

class WaitDialog (object):
    """Application options"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.app = main_window.app
        self._task = None

        self._poll_time = 200
    
    def show(self, title, message, task):
        self.xml = gtk.glade.XML(get_resource("rc", "takenote.glade"),
                                 "wait_dialog")
        self.dialog = self.xml.get_widget("wait_dialog")
        self.xml.signal_autoconnect(self)
        self.dialog.set_transient_for(self.main_window)
        self.text = self.xml.get_widget("wait_text_label")
        self.progressbar = self.xml.get_widget("wait_progressbar")

        self.dialog.set_title(title)
        self.text.set_text(message)
        self._task = task
        #self._task.change_event.add(self._on_task_update)
        self._task.run()


        self.dialog.show()
        gobject.timeout_add(100, self._on_idle)
        self.dialog.run()
        self._task.join()


    def _on_idle(self):
        """Idle callback"""
        
        if not self._task.is_stopped():
            # keep idling

            percent = self._task.get_percent()

            if percent is None:            
                self.progressbar.pulse()
            else:
                self.progressbar.set_fraction(percent)

            # filter for messages we process
            messages = filter(lambda x: isinstance(x, tuple) and len(x) == 2,
                              self._task.get_messages())
            texts = filter(lambda (a,b): a == "text", messages)
            details = filter(lambda (a,b): a == "detail", messages)

            if len(texts) > 0:
                self.text.set_text(texts[-1][1])
            if len(details) > 0:
                self.progressbar.set_text(details[-1][1])

            #time.sleep(.05)
            gobject.timeout_add(50, self._on_idle)
            return False
        else:
            # kill dialog and stop idling
            self.dialog.destroy()
            return False

    def _on_task_update(self):
        pass

        
        

    def on_cancel_button_clicked(self, button):
        """Attempt to stop the task"""

        self.text.set_text("Canceling...")
        self._task.stop()

        
