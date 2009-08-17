import os, shutil, unittest, thread, threading, traceback, sys

# keepnote imports
import keepnote
from keepnote import notebook as notebooklib




class TestCaseNotebookIndex (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_notebook_lookup_node(self):        

        export_filename = "test/data/notebook_export"
        app = keepnote.KeepNote()
        ext = app.get_extension("export_html")
        
        book = notebooklib.NoteBook()
        book.load("test/data/notebook-v3")

        if os.path.exists(export_filename):
            shutil.rmtree(export_filename)

        ext.export_notebook(book, export_filename)
        
        
        

        
notebook_index_suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseNotebookIndex)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(notebook_index_suite)

