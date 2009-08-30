import os, shutil, unittest, thread, threading, traceback, sys

# keepnote imports
from keepnote import notebook



class TestCaseNotebookIndex (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_node_url(self):

        urls = ["nbk://bad_url",
                "nbk:///0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"]
        
        for url in urls:
            print url
            if notebook.is_node_url(url):
                host, nodeid = notebook.parse_node_url(url)                
                print host, nodeid
            else:
                print "not a node url"
            print 


    def test_notebook_lookup_node(self):        

        nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"
        path = os.path.join("test/data/notebook-v3", "stress tests")
        
        book = notebook.NoteBook()
        book.load("test/data/notebook-v3")
        
        print "indexing..."
        for node in book._index.index_all(): pass

        path2 = book.get_node_path_by_id(nodeid)
        self.assertEqual(path, path2)
        book.close()

        book2 = notebook.NoteBook()
        book2.load("test/data/notebook-v3")
        
        path2 = book2.get_node_path_by_id(nodeid)
        self.assertEqual(path, path2)
        book2.close()


    def test_notebook_move_deja_vu(self):

        book = notebook.NoteBook()
        book.load("test/data/notebook-v3")
        #book._index.index_all()

        # get the page u"Deja vu")
        nodeids = book._index.search_titles(u"vu")
        print nodeids
        nodea = book.get_node_by_id(nodeids[0][0])

        nodeids = book._index.search_titles("e")
        nodeb = book.get_node_by_id(nodeids[0][0])

        print
        print nodea.get_path()
        print nodeb.get_path()
        parenta = nodea.get_parent()
        
        nodea.move(nodeb)

        print "new path:", nodea.get_path()
        nodea.move(parenta)
        print "back path:", nodea.get_path()



    def test_notebook_title(self):

        nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"        
        path = os.path.join("test/data/notebook-v3", "stress tests")
        
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
                              os.path.join("test/data/notebook-v3", "stress tests"))
                    #book.save()

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

