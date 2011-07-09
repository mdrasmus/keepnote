
from testing import *

import os, shutil, unittest, thread, threading, traceback, sys, time

# keepnote imports
import keepnote
from keepnote import notebook



class Speed (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_open(self):

        filename = "test/data/notebook-v5"
        app = keepnote.KeepNote("keepnote")

        start = time.time()
        book = app.get_notebook(filename)

        def walk(node):
            for child in node.get_children():
                walk(child)
        walk(book)
        
        t = time.time() - start
        print "seconds: ", t
        book.close()
        

    def test_new_node(self):
        
        clean_dir("test/tmp/notebook_new_node")
        shutil.copytree("test/data/notebook-v5",
                        "test/tmp/notebook_new_node")

        book = notebook.NoteBook()
        book.load("test/tmp/notebook_new_node")
        for n in book.index_all(): pass

        start = time.time()

        n = book.get_node_by_id("8827eb8f-f7eb-4ef4-a0e5-8a5c00f8dd18")
        print n
        for i in range(100):
            print i
            notebook.new_page(n, str(i))

        t = time.time() - start
        print "seconds: ", t
        book.close()


        

if __name__ == "__main__":
    unittest.main()

