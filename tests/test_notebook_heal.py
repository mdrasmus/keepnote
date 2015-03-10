
# python imports
import unittest
import os
import time

# keepnote imports
from keepnote import notebook
import keepnote.notebook.connection.fs as fs
from keepnote.notebook.connection import ConnectionError

from . import make_clean_dir, TMP_DIR

_tmpdir = os.path.join(TMP_DIR, 'notebook_heal')


class Heal (unittest.TestCase):

    def test_no_index(self):

        # initialize two notebooks
        make_clean_dir(_tmpdir)

        book = notebook.NoteBook()
        book.create(_tmpdir + "/n1")
        book.close()

        # remove index
        os.remove(_tmpdir + "/n1/__NOTEBOOK__/index.sqlite")

        # try to load again
        book = notebook.NoteBook()
        book.load(_tmpdir + "/n1")
        self.assertTrue("index.sqlite" in os.listdir(
            _tmpdir + "/n1/__NOTEBOOK__"))
        book.close()

    def test_bad_index(self):

        # initialize two notebooks
        make_clean_dir(_tmpdir)

        book = notebook.NoteBook()
        book.create(_tmpdir + "/n1")
        book.close()

        # corrupt index
        out = open(_tmpdir + "/n1/__NOTEBOOK__/index.sqlite", "w")
        out.write("jsakhdfjhdsfh")
        out.close()

        # try to load again
        book = notebook.NoteBook()
        book.load(_tmpdir + "/n1")

        self.assertFalse(book._conn._index.is_corrupt())
        self.assertTrue(book.index_needed())

        book.close()

    def test_bad_node(self):

        # initialize two notebooks
        make_clean_dir(_tmpdir)

        book = notebook.NoteBook()
        book.create(_tmpdir + "/n1")
        book.close()

        # corrupt node
        out = open(_tmpdir + "/n1/node.xml", "w")
        out.write("***bad node***")
        out.close()

        # try to load again, should raise error.
        def func():
            book = notebook.NoteBook()
            book.load(_tmpdir + "/n1")

        self.assertRaises(ConnectionError, func)

    def test_bad_notebook_pref(self):

        # initialize two notebooks
        make_clean_dir(_tmpdir)

        book = notebook.NoteBook()
        book.create(_tmpdir + "/n1")
        book.close()

        # corrupt preference data
        out = open(_tmpdir + "/n1/notebook.nbk", "w")
        out.write("***bad preference***")
        out.close()

        # try to load again
        def func():
            book = notebook.NoteBook()
            book.load(_tmpdir + "/n1")
        self.assertRaises(notebook.NoteBookError, func)

    def test_tamper(self):

        struct = [["a", ["a1"], ["a2"], ["a3"]],
                  ["b", ["b1"], ["b2",
                                 ["c1"], ["c2"]]]]

        def make_notebook(node, children):
            for child in children:
                name = child[0]
                node2 = notebook.new_page(node, name)
                make_notebook(node2, child[1:])

        # initialize a notebook
        make_clean_dir(_tmpdir + "/notebook_tamper")

        print "creating notebook"
        book = notebook.NoteBook()
        book.create(_tmpdir + "/notebook_tamper/n1")
        make_notebook(book, struct)
        book.close()

        print "system"
        os.system((
            "sqlite3 %s/notebook_tamper/n1/__NOTEBOOK__/index.sqlite "
            "'select mtime from NodeGraph where parentid == \"" +
            notebook.UNIVERSAL_ROOT + "\";'") % _tmpdir)

        time.sleep(1)

        print fs.get_path_mtime(_tmpdir + u"/notebook_tamper/n1")
        fs.mark_path_outdated(_tmpdir + u"/notebook_tamper/n1")
        print fs.get_path_mtime(_tmpdir + u"/notebook_tamper/n1")

        print "reopening notebook 1"
        book = notebook.NoteBook()
        book.load(_tmpdir + "/notebook_tamper/n1")
        book.close()

        print "reopening notebook 2"
        book = notebook.NoteBook()
        book.load(_tmpdir + "/notebook_tamper/n1")
        book.close()
