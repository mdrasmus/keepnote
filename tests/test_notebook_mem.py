
# python imports
import sys
import unittest
from StringIO import StringIO

# keepnote imports
from keepnote import notebook
from keepnote.notebook.connection import mem


def display_notebook(node, depth=0, out=sys.stdout):
    print >>out, " " * depth + node.get_attr("title")
    for child in node.get_children():
        display_notebook(child, depth+2, out)


class Mem (unittest.TestCase):

    def test_struct(self):

        # initialize a notebook
        book1 = notebook.NoteBook()
        book1.create("n1", mem.NoteBookConnectionMem())
        book1.set_attr("title", "root")

        # populate book
        for i in range(5):
            node = notebook.new_page(book1, "a%d" % i)
            for j in range(2):
                notebook.new_page(node, "b%d-%d" % (i, j))

        expected = """\
root
  a0
    b0-0
    b0-1
  a1
    b1-0
    b1-1
  a2
    b2-0
    b2-1
  a3
    b3-0
    b3-1
  a4
    b4-0
    b4-1
  Trash
"""
        # assert structure is correct.
        out = StringIO()
        display_notebook(book1, out=out)
        self.assertEqual(out.getvalue(), expected)

        # edit book
        nodeid = book1.search_node_titles("a1")[0][0]
        node1 = book1.get_node_by_id(nodeid)

        nodeid = book1.search_node_titles("b3-0")[0][0]
        node2 = book1.get_node_by_id(nodeid)

        node1.move(node2)

        expected = """\
root
  a0
    b0-0
    b0-1
  a2
    b2-0
    b2-1
  a3
    b3-0
      a1
        b1-0
        b1-1
    b3-1
  a4
    b4-0
    b4-1
  Trash
"""

        # Assert new structure.
        out = StringIO()
        display_notebook(book1, out=out)
        self.assertEqual(out.getvalue(), expected)

        # Assert that file contents are provided.
        self.assertEqual(node1.open_file("page.html").read(),
                         notebook.BLANK_NOTE)
