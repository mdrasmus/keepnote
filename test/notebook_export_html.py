import os, shutil, unittest, thread, threading, traceback, sys

# keepnote imports
import keepnote
from keepnote import notebook as notebooklib




class TestCaseNotebookIndex (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_notebook_lookup_node(self):        

        export_filename = "test/tmp/notebook_export"
        app = keepnote.KeepNote()
        app.init()
        ext = app.get_extension("export_html")
        
        print "loading notebook..."
        book = notebooklib.NoteBook()
        book.load("test/data/notebook-v3")

        print "clearing output..."
        if os.path.exists(export_filename):
            shutil.rmtree(export_filename)

        print "exporting..."
        ext.export_notebook(book, export_filename)
        
        
if __name__ == "__main__":
    unittest.main()



