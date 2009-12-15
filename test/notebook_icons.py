import os, shutil, unittest, thread, threading, traceback, sys

import gtk

# keepnote imports
import keepnote.gui
from keepnote import notebook



class TestCaseNotebookIndex (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_notebook_read_icons(self):        
        
        book = notebook.NoteBook()
        book.load("test/data/notebook-v3")
        book.pref.set_quick_pick_icons(["x.png"])
        book.set_preferences_dirty()
        book.save()

        self.assertEqual(book.pref.get_quick_pick_icons(), ["x.png"])

        print open("test/data/notebook-v3/notebook.nbk").read()

        book.load("test/data/notebook-v3")

        self.assertEqual(book.pref.get_quick_pick_icons(), ["x.png"])

        print book.pref.get_quick_pick_icons()
        

    def test_notebook_read_icons2(self):        
        
        app = keepnote.gui.KeepNote()
        book = app.get_notebook("test/data/notebook-v3")

        print book.pref.get_quick_pick_icons()



    def test_notebook_read_icons3(self):        

        app = keepnote.gui.KeepNote()
        win = app.new_window()
        book = win.open_notebook("test/data/notebook-v3")

        print book.pref.get_quick_pick_icons()

        gtk.main()

        book.pref.set_quick_pick_icons(["x2.png"])
        book.set_preferences_dirty()

        print book.pref.get_quick_pick_icons()
        win.close_notebook()

        print open("test/data/notebook-v3/notebook.nbk").read()

        #gtk.main()




        
notebook_index_suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseNotebookIndex)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(notebook_index_suite)

