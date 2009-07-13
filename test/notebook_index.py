import os, shutil, unittest, thread, threading, traceback, sys

# keepnote imports
from keepnote import notebook



class TestCaseNotebookIndex (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_notebook_lookup_node(self):

        nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"
        path = "test/data/notebook-v3/stress tests"
        
        book = notebook.NoteBook()
        book.load("test/data/notebook-v3")
        
        path2 = book.get_node_path_by_id(nodeid)
        self.assertEqual(path, path2)
        book.close()

        book2 = notebook.NoteBook()
        book2.load("test/data/notebook-v3")
        
        path2 = book2.get_node_path_by_id(nodeid)
        self.assertEqual(path, path2)
        book2.close()


    def test_notebook_lookup_node2(self):

        nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"
        path = "test/data/notebook-v3/stress tests"
        
        book = notebook.NoteBook()
        book.load("test/data/notebook-v3")

        path2 = book.get_node_path_by_id(nodeid)
        self.assertEqual(path, path2)
        book.save()

        book2 = notebook.NoteBook()
        book2.load("test/data/notebook-v3")

        path2 = book2.get_node_path_by_id(nodeid)
        self.assertEqual(path, path2)
        book2.save()


    def test_notebook_title(self):

        nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"
        path = "test/data/notebook-v3/stress tests"
        
        book = notebook.NoteBook()
        book.load("test/data/notebook-v3")

        print book._index.search_titles("STRESS")
        print book._index.search_titles("aaa")
        

    def test_notebook_threads(self):

        test = self

        print
        book = notebook.NoteBook()
        book.load("test/data/notebook-v3")
        book.save()

        class Task (threading.Thread):

            def run(self):
                try:
                    print "loading..."

                    nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"
                    path = book.get_node_path_by_id(nodeid)
                    print "path:", path
                    test.assertEqual(path, 
                              "test/data/notebook-v3/stress tests")
                    book.save()

                except Exception, e:
                    print "ERROR:"
                    traceback.print_exception(type(e), e, sys.exc_info()[2])
                    raise e
                

        task = Task()
        task.start()
        task.join()

        book.save()

        

        
notebook_index_suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseNotebookIndex)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(notebook_index_suite)

