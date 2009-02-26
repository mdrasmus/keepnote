"""

   Change Node Icon Sub Menu

"""


# pygtk imports
import pygtk
pygtk.require('2.0')
import gobject
import gtk

import keepnote.gui



class IconMenu (gtk.Menu):
    """Icon picker menu"""

    def __init__(self):
        gtk.Menu.__init__(self)

        self.width = 4
        self.posi = 0
        self.posj = 0

        for iconfile in keepnote.gui.builtin_icons:                    
            self.add_icon(iconfile)

        # separator
        item = gtk.SeparatorMenuItem()
        item.show()
        self.append(item)

        # default icon
        self.default_icon = gtk.MenuItem("_Default Icon")
        self.default_icon.connect("activate",
                                  lambda w: self.emit("set-icon", None))
        self.default_icon.show()
        self.append(self.default_icon)

        # new icon
        self.new_icon = gtk.MenuItem("_New Icon...")
        self.new_icon.show()
        self.append(self.new_icon)
        

    def append_grid(self, item):
        self.attach(item, self.posj, self.posj+1, self.posi, self.posi+1)
        
        self.posj += 1
        if self.posj >= self.width:
            self.posj = 0
            self.posi += 1

    def append(self, item):
        
        # reset posi, posj
        if self.posj > 0:
            self.posi += 1
            self.posj = 0

        gtk.Menu.append(self, item)

    def add_icon(self, iconfile):

        child = gtk.MenuItem("")
        child.remove(child.child)
        img = gtk.Image()
        iconfile2 = keepnote.gui.lookup_icon_filename(None, iconfile)
        img.set_from_file(iconfile2)
        child.add(img)
        child.child.show()
        child.show()
        child.connect("activate",
                      lambda w: self.emit("set-icon", iconfile))
        self.append_grid(child)


gobject.type_register(IconMenu)
gobject.signal_new("set-icon", IconMenu, gobject.SIGNAL_RUN_LAST, 
           gobject.TYPE_NONE, (object,))

