


from test.testing import *

# python imports
import unittest, os, sys, shutil, time

# keepnote imports
from keepnote import notebook, safefile
import keepnote.notebook.connection as connlib
import keepnote.notebook.connection.fs as fs


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

        c1id = book.get_children()[1].get_children()[1].get_children()[0]

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

        c1id = book.get_children()[1].get_children()[1].get_children()[0].get_attr("nodeid")

        book.close()

        print "load"
        book = notebook.NoteBook()
        book.load("test/tmp/notebook_struct/n1")
        
        c1 = book.get_node_by_id(c1id)
        print "found", c1.get_title()

        book.close()

        


        
if __name__ == "__main__":
    test_main()

