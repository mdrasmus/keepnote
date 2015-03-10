
# python imports
import os
import unittest

# keepnote imports
from keepnote import notebook
import keepnote.notebook.sync as sync

from . import clean_dir, makedirs, TMP_DIR


# root path for test data
_datapath = os.path.join(TMP_DIR, 'notebook_sync')


class Sync (unittest.TestCase):

    def test_sync(self):

        # initialize two notebooks
        clean_dir(_datapath + "/n1")
        clean_dir(_datapath + "/n2")
        makedirs(_datapath)

        notebook1 = notebook.NoteBook()
        notebook1.create(_datapath + "/n1")

        notebook2 = notebook.NoteBook()
        notebook2.create(_datapath + "/n2")

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
        self.assertTrue(attr)

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
