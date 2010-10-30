
# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk





class PopupWindow (gtk.Window):
    """A customizable popup window"""

    def __init__(self, parent):
        gtk.Window.__init__(self, gtk.WINDOW_POPUP)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_MENU)
        self.set_transient_for(parent.get_toplevel())
        self.set_flags(gtk.CAN_FOCUS)
        self.add_events(gtk.gdk.KEY_PRESS_MASK | 
                        gtk.gdk.KEY_RELEASE_MASK)


        self._parent = parent
        self._parent.get_toplevel().connect("configure-event", 
                                            self._on_configure_event)

        # coordinates of popup
        self._x = 0
        self._y = 0
        self._y2 = 0


    def _on_configure_event(self, widget, event):
        self.move_on_parent(self._x, self._y, self._y2)

    def move_on_parent(self, x, y, y2):
        """Move popup relative to parent widget"""

        win = self._parent.get_parent_window()
        if win is None:
            return

        # remember coordinates
        self._x = x
        self._y = y
        self._y2 = y2

        # get screen dimensions
        screenw = gtk.gdk.screen_width()
        screenh = gtk.gdk.screen_height()

        # account for window
        wx, wy = win.get_origin()
        x3 = wx
        y3 = wy

        # account for widget
        rect = self._parent.get_allocation()
        x3 += rect.x
        y3 += rect.y 

        # get size of popup
        w, h = self.child.size_request()
        self.resize(w, h)
        
        # perform move
        if y + y3 + h < screenh:
            # drop down
            self.move(x + x3, y + y3)
        else:
            # drop up
            self.move(x + x3, y2 + y3 - h)
