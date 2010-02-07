import os, shutil, unittest, thread, threading, traceback, sys, time

# keepnote imports
import keepnote
from keepnote import notebook



class NoteBookSpeed (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test1(self):

        filename = "test/data/notebook-v3"
        app = keepnote.KeepNote("keepnote")

        start = time.time()
        book = app.get_notebook(filename)

        def walk(node):
            for child in node.get_children():
                walk(child)
        walk(book)
        
        t = time.time() - start
        print "seconds: ", t
        

        
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    NoteBookSpeed)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)

