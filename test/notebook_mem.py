
# python imports
import os, sys, shutil

from testing import *

# keepnote imports
from keepnote import notebook, safefile
import keepnote.notebook.connection as connlib
from keepnote.notebook.connection import mem
from keepnote import notebook as notebooklib


def display_notebook(node, depth=0):
    print " " * depth + node.get_attr("title") + ": " + node.get_attr("nodeid")
    for child in node.get_children():
        display_notebook(child, depth+2)
    

class Mem (unittest.TestCase):

    def test1(self):

        # initialize two notebooks
        book1 = notebook.NoteBook()
        book1.create("n1", mem.NoteBookConnectionMem())
        book1.set_attr("title", "root")

        # populate book1
        for i in range(5):
            node = notebooklib.new_page(book1, "a%d" % i)
            for j in range(2):
                notebooklib.new_page(node, "b%d-%d" % (i, j))

        display_notebook(book1)

        # edit book1
        nodeid = book1.search_node_titles("a1")[0][0]
        node1 = book1.get_node_by_id(nodeid)

        nodeid = book1.search_node_titles("b3-0")[0][0]
        node2 = book1.get_node_by_id(nodeid)

        node1.move(node2)

        print "-" * 30
        display_notebook(book1)

        
        print node1.open_file("page.html").read()

        
if __name__ == "__main__":
    test_main()

