
# python imports
import unittest, os, sys, shutil

# keepnote imports
from keepnote import notebook, safefile
import keepnote.notebook.connection as connlib
import keepnote.notebook.sync as sync


def clean_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path)

def makedirs(path):
    if not os.path.exists(path):
        os.makedirs(path)

class Sync (unittest.TestCase):

    def test_sync(self):

        # initialize two notebooks
        clean_dir("test/tmp/notebook_sync/n1")
        clean_dir("test/tmp/notebook_sync/n2")
        makedirs("test/tmp/notebook_sync")

        notebook1 = notebook.NoteBook()
        notebook1.create("test/tmp/notebook_sync/n1")

        notebook2 = notebook.NoteBook()
        notebook2.create("test/tmp/notebook_sync/n2")

        print list(notebook1.list_dir())
        

        # create a new node in notebook1
        n = notebook1.new_child("text/html", "node1")
        for i in range(5):
            out = n.open_file("file" + str(i), "w")
            out.write("hello" + str(i))
            out.close()
        n.open_file("dir/hello", "w").close()

        # transfer node to notebook2 (rename parent)
        attr = dict(n._attr)
        attr["parentids"] = [notebook2.get_attr("nodeid")]
        sync.sync_node(n.get_attr("nodeid"), 
                       notebook1._conn,
                       notebook2._conn,
                       attr)

        # check that node was transfered
        attr = notebook2._conn.read_node(n.get_attr("nodeid"))
        print attr
        self.assert_(attr is not None)


        # rename node and increase modified time
        # transfer should detect conflict and use newer node
        attr["title"] = "node2"
        attr["modified_time"] += 1
        n.open_file("new_file", "w").close()
        n.delete_file("file3")
        sync.sync_node(attr["nodeid"], 
                       notebook1._conn,
                       notebook2._conn,
                       attr)
        
        # check for newer node
        attr = notebook2._conn.read_node(n.get_attr("nodeid"))
        self.assert_(attr["title"] == "node2")


        # rename node and decrease modified time
        # transfer should detect conflict and reject transfer
        attr["title"] = "node3"
        attr["modified_time"] -= 10
        sync.sync_node(attr["nodeid"], 
                       notebook1._conn,
                       notebook2._conn,
                       attr)

        # check for original node
        attr = notebook2._conn.read_node(n.get_attr("nodeid"))
        self.assert_(attr["title"] == "node2")
        notebook2.close()


    def test_files(self):

        # initialize two notebooks
        clean_dir("test/tmp/notebook_sync/n1")
        clean_dir("test/tmp/notebook_sync/n2")
        makedirs("test/tmp/notebook_sync")

        notebook1 = notebook.NoteBook()
        notebook1.create("test/tmp/notebook_sync/n1")

        notebook2 = notebook.NoteBook()
        notebook2.create("test/tmp/notebook_sync/n2")
        
        # create a new node in notebook1 with several files
        n = notebook1.new_child("text/html", "node1")
        for i in range(5):
            out = n.open_file("file" + str(i), "w")
            out.write("hello" + str(i))
            out.close()
        n.create_dir("dir")
        n.open_file("dir/hello", "w").close()
        
        # list files
        nodeid = n.get_attr("nodeid")
        print n.get_attr("nodeid"), notebook1._conn.has_node(nodeid)
        files = set(u"file" + str(i) for i in range(5))
        files.add(u"dir/")
        self.assertEqual(set(n.list_dir()), 
                         files)
        self.assertEqual(list(n.list_dir("dir/")), ["hello"])
        print list(n.list_dir())
        print list(n.list_dir("dir/"))
        try:
            print list(n.list_dir("dir-noexist/"))
            assert False
        except connlib.UnknownFile:
            # this exception should occur
            pass
        
        notebook1.close()
        notebook2.close()


        
if __name__ == "__main__":
    unittest.main()

