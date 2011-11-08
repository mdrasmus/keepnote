import os, shutil, unittest, thread, threading, traceback, sys

# keepnote imports
from keepnote import notebook, safefile

from test.testing import *


class Index (unittest.TestCase):
    
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
        path = os.path.join("test/data/notebook", "stress tests")
        
        book = notebook.NoteBook()
        book.load("test/data/notebook")

        path2 = book.get_node_path_by_id(nodeid)
        self.assertEqual(path, path2)
        book.close()

        book2 = notebook.NoteBook()
        book2.load("test/data/notebook")
        
        path2 = book2.get_node_path_by_id(nodeid)
        self.assertEqual(path, path2)
        book2.close()


    def test_notebook_move_deja_vu(self):

        book = notebook.NoteBook()
        book.load("test/data/notebook")

        # get the page u"Deja vu")
        nodeids = book.search_node_titles(u"vu")
        print nodeids
        nodea = book.get_node_by_id(nodeids[0][0])

        nodeids = book.search_node_titles("e")
        nodeb = book.get_node_by_id(nodeids[0][0])

        print
        print nodea.get_path()
        print nodeb.get_path()
        parenta = nodea.get_parent()
        
        nodea.move(nodeb)

        print "new path:", nodea.get_path()
        nodea.move(parenta)
        print "back path:", nodea.get_path()

        book.close()



    def test_notebook_title(self):

        book = notebook.NoteBook()
        book.load("test/data/notebook")

        print book.search_node_titles("STRESS")
        print book.search_node_titles("aaa")

        self.assert_(len(book.search_node_titles("STRESS")) > 0)


    def test_notebook_threads(self):

        test = self

        print
        book = notebook.NoteBook()
        book.load("test/data/notebook")
        book.save()

        class Task (threading.Thread):

            def run(self):
                try:
                    print "loading..."

                    nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"
                    path = book.get_node_path_by_id(nodeid)
                    print "path:", path
                    test.assertEqual(path,
                              os.path.join("test/data/notebook", "stress tests"))
                    #book.save()

                except Exception, e:
                    print "ERROR:"
                    traceback.print_exception(type(e), e, sys.exc_info()[2])
                    raise e
                

        task = Task()
        task.start()
        task.join()

        book.save()
        book.close()


    def test_notebook_threads2(self):

        test = self
        error = False

        print
        book = notebook.NoteBook()
        book.load("test/data/notebook")
        book.save()

        nodeid = "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"

        def walk(node):
            for child in node.get_children():
                walk(child)


        class Task (threading.Thread):

            def run(self):
                try:
                    print "loading..."                    
                    #node = book.get_node_by_id(nodeid)
                    walk(book)

                except Exception, e:
                    error = True
                    print "ERROR:"
                    traceback.print_exception(type(e), e, sys.exc_info()[2])
                    raise e
                
        #node = book.get_node_by_id(nodeid)

        task = Task()
        task.start()
        task.join()

        walk(book)
        
        book.close()

        self.assert_(not error)


    def test_fts3(self):
        
        import sqlite3 as sqlite
        
        print sqlite.sqlite_version

        con = sqlite.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE email USING fts3(content TEXT);")

        con.execute("INSERT INTO email VALUES ('hello there how are you');")
        con.execute("INSERT INTO email VALUES ('this is tastier');")

        print list(
            con.execute("SELECT * FROM email WHERE content MATCH 'tast*';"))


    def test_fulltext(self):
        
        import sqlite3 as sqlite
        
        print sqlite.sqlite_version

        con = sqlite.connect(":memory:")
        con.execute("""CREATE VIRTUAL TABLE notes USING 
                     fts3(nodeid TEXT, content TEXT);""")

        book = notebook.NoteBook()
        book.load("test/data/notebook")
        
        def walk(node):

            if node.get_attr("content_type") == notebook.CONTENT_TYPE_PAGE:
                text = "".join(notebook.read_data_as_plain_text(safefile.open(node.get_data_file(), codec="utf-8")))
                
                con.execute("INSERT INTO notes VALUES (?, ?)", 
                            (node.get_attr("nodeid"), text))

            for child in node.get_children():
                walk(child)

        walk(book)


        print list(
            con.execute("SELECT nodeid FROM notes WHERE content MATCH '*hello*';"))

        book.close()


    def test_concurrent(self):
        
        book1 = notebook.NoteBook()
        book1.load("test/data/notebook")

        book2= notebook.NoteBook()
        book2.load("test/data/notebook")

        print list(book1.iter_attr())
        print list(book2.iter_attr())

        book1.close()
        book2.close()


    def test_index_all(self):

        book = notebook.NoteBook()
        book.load("test/data/notebook")

        for node in book.index_all():
            print node

        book.close()


        
if __name__ == "__main__":
    test_main()

