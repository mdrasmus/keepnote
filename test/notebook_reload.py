import os, shutil, unittest, thread, threading, traceback, sys

from testing import *

# keepnote imports
import keepnote
from keepnote import notebook



class NoteBookReload (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_notebook_lookup_node(self):        

        nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"
        filename = "test/data/notebook-v3"
        path = os.path.join(filename, "stress tests")
        
        app = keepnote.KeepNote("keepnote")
        book = app.get_notebook(filename)
        print "opened '%s'" % book.get_title()
        print "\t".join(["%d. '%s'" % (i+1, x.get_title()) 
                         for i, x in enumerate(app.iter_notebooks())])
        app.close_notebook(book)

        print "notebook closed"

        print "\t".join(["%d. '%s'" % (i+1, x.get_title()) 
                         for i, x in enumerate(app.iter_notebooks())])

        self.assert_(len(list(app.iter_notebooks())) == 0)


if __name__ == "__main__":
    test_main()

