import os, shutil, unittest, thread, threading, traceback, sys

import gtk

# keepnote imports
import keepnote.gui
from keepnote import notebook

from test.testing import *


class Tests (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_notebook_read_icons(self):        
        
        book = notebook.NoteBook()
        book.load("test/data/notebook-v4")
        book.pref.set_quick_pick_icons(["x.png"])
        book.set_preferences_dirty()
        book.save()

        self.assertEqual(book.pref.get_quick_pick_icons(), ["x.png"])

        print open("test/data/notebook-v4/notebook.nbk").read()

        book.load("test/data/notebook-v4")

        self.assertEqual(book.pref.get_quick_pick_icons(), ["x.png"])

        print book.pref.get_quick_pick_icons()
        book.close()
        

    def test_notebook_read_icons2(self):        
        
        app = keepnote.gui.KeepNote()
        app.init()
        book = app.get_notebook("test/data/notebook-v4")

        print book.pref.get_quick_pick_icons()
        book.close()



    def test_notebook_read_icons3(self):        

        app = keepnote.gui.KeepNote()
        app.init()
        win = app.new_window()
        book = win.open_notebook("test/data/notebook-v4")

        print book.pref.get_quick_pick_icons()

        gtk.main()

        book.pref.set_quick_pick_icons(["x2.png"])
        book.set_preferences_dirty()

        print book.pref.get_quick_pick_icons()
        win.close_notebook()

        print open("test/data/notebook-v4/notebook.nbk").read()


    def test_install_icon(self):
        
        book = notebook.NoteBook("test/data/notebook-v4")
        book.load()

        icons = []

        print "before", os.listdir("test/data/notebook-v4/__NOTEBOOK__/icons")
        
        book.install_icon("share/icons/gnome/16x16/mimetypes/zip.png")
        book.install_icon("share/icons/gnome/16x16/mimetypes/zip.png")

        book.install_icons(
            "keepnote/images/node_icons/folder-orange.png",
            "keepnote/images/node_icons/folder-orange-open.png")
        book.install_icons(
            "keepnote/images/node_icons/folder-orange.png",
            "keepnote/images/node_icons/folder-orange-open.png")

        book.save()

        print "installed", os.listdir("test/data/notebook-v4/__NOTEBOOK__/icons")

        icons = os.listdir("test/data/notebook-v4/__NOTEBOOK__/icons")

        for icon in icons:
            book.uninstall_icon(icon)

        print "clean up", os.listdir("test/data/notebook-v4/__NOTEBOOK__/icons")

        book.close()


if __name__ == "__main__":
    test_main()

