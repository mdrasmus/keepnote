
# python imports
import unittest
import os

# keepnote imports
from keepnote import notebook
import keepnote.notebook.connection.fs as fs
from keepnote.notebook import new_nodeid
from testing import make_clean_dir, clean_dir


def display_notebook(node, depth=0):
    print "  " * depth,
    print node.get_title()

    for child in node.get_children():
        display_notebook(child, depth+1)


def make_notebook(node, children):
    for child in children:
        name = child[0]
        node2 = notebook.new_page(node, name)
        make_notebook(node2, child[1:])


class Test (unittest.TestCase):

    def test_move(self):

        struct = [["a", ["a1"], ["a2"], ["a3"]],
                  ["b", ["b1"], ["b2",
                                 ["c1"], ["c2"]]]]

        # initialize a notebook
        make_clean_dir("test/tmp/notebook_struct")

        print "creating notebook"
        book = notebook.NoteBook()
        book.create("test/tmp/notebook_struct/n1")
        make_notebook(book, struct)

        self.assertTrue(
            book.get_children()[1].get_children()[1].get_children()[0])

        book.close()

        print "load"
        book = notebook.NoteBook()
        book.load("test/tmp/notebook_struct/n1")

        a2 = book.get_children()[0].get_children()[1]
        b = book.get_children()[1]
        a2.move(b)

        display_notebook(book)
        book.close()

    def test_rename(self):

        struct = [["a", ["a1"], ["a2"], ["a3"]],
                  ["b", ["b1"], ["b2",
                                 ["c1"], ["c2"]]]]

        # initialize a notebook
        make_clean_dir("test/tmp/notebook_struct")

        print "creating notebook"
        book = notebook.NoteBook()
        book.create("test/tmp/notebook_struct/n1")
        make_notebook(book, struct)

        c1 = book.get_children()[1].get_children()[1].get_children()[0]
        c1.rename("new c1")

        book.close()

        print "load"
        book = notebook.NoteBook()
        book.load("test/tmp/notebook_struct/n1")
        display_notebook(book)
        book.close()

    def test_random_access(self):

        struct = [["a", ["a1"], ["a2"], ["a3"]],
                  ["b", ["b1"], ["b2",
                                 ["c1"], ["c2"]]]]

        # initialize a notebook
        make_clean_dir("test/tmp/notebook_struct")

        print "creating notebook"
        book = notebook.NoteBook()
        book.create("test/tmp/notebook_struct/n1")
        make_notebook(book, struct)

        c1id = (book.get_children()[1]
                .get_children()[1].get_children()[0].get_attr("nodeid"))

        book.close()

        print "load"
        book = notebook.NoteBook()
        book.load("test/tmp/notebook_struct/n1")

        c1 = book.get_node_by_id(c1id)
        print "found", c1.get_title()

        book.close()

    def test_orphans(self):

        clean_dir("test/tmp/conn")

        # create new notebook
        conn = fs.NoteBookConnectionFS()
        conn.connect("test/tmp/conn")
        rootid = new_nodeid()
        conn.create_node(rootid, {"nodeid": rootid,
                                  "parentids": [],
                                  "key": 12})

        # check orphan dir
        assert os.path.exists("test/tmp/conn/__NOTEBOOK__/orphans")

        # make orphan
        nodeid = new_nodeid()
        conn.create_node(nodeid, {"nodeid": nodeid,
                                  "aaa": 3.4})
        attr = conn.read_node(nodeid)
        print attr

        # check orphan node dir
        assert os.path.exists("test/tmp/conn/__NOTEBOOK__/orphans/%s/%s"
                              % (nodeid[:2], nodeid[2:]))

        # update orphan
        attr["aaa"] = 0
        conn.update_node(nodeid, attr)
        attr = conn.read_node(nodeid)
        print attr

        # check orphan node dir
        print open("test/tmp/conn/__NOTEBOOK__/orphans/%s/%s/node.xml"
                   % (nodeid[:2], nodeid[2:])).read()

        # move orphan out of orphandir
        attr["parentids"] = [rootid]
        conn.update_node(nodeid, attr)
        print conn.read_node(nodeid)

        # check orphan node dir is gone
        assert not os.path.exists("test/tmp/conn/__NOTEBOOK__/orphans/%s/%s"
                                  % (nodeid[:2], nodeid[2:]))

        # move node into orphandir
        attr["parentids"] = []
        conn.update_node(nodeid, attr)
        print conn.read_node(nodeid)

        # check orphan node dir is gone
        assert os.path.exists("test/tmp/conn/__NOTEBOOK__/orphans/%s/%s"
                              % (nodeid[:2], nodeid[2:]))
