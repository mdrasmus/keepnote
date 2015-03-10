# -*- coding: utf-8 -*-

import os
import unittest
from StringIO import StringIO
import sqlite3 as sqlite
import sys
import threading
import time
import traceback

# keepnote imports
from keepnote import notebook

from . import clean_dir, TMP_DIR


# test notebook
_notebook_file = os.path.join(TMP_DIR, "notebook")


def write_content(page, text):
    with page.open_file(notebook.PAGE_DATA_FILE, 'w') as out:
        out.write(notebook.NOTE_HEADER)
        out.write(text)
        out.write(notebook.NOTE_FOOTER)

    # Trigger re-indexing of full text.
    page.save(True)


class Index (unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Create a simple notebook to test against.
        clean_dir(_notebook_file)
        cls._notebook = book = notebook.NoteBook()
        book.create(_notebook_file)

        # create simple nodes
        page1 = notebook.new_page(book, 'Page 1')
        pagea = notebook.new_page(page1, 'Page A')
        write_content(pagea, 'hello world')
        pageb = notebook.new_page(page1, 'Page B')
        write_content(pageb, 'why hello, what is new?')
        pagec = notebook.new_page(page1, 'Page C')
        write_content(pagec, 'brand new world')

        pagex = notebook.new_page(pageb, 'Page X')
        cls._pagex_nodeid = pagex.get_attr('nodeid')

        notebook.new_page(book, 'Page 2')

        notebook.new_page(book, 'Page 3')
        book.close()

    @classmethod
    def tearDownClass(cls):
        pass

    def test_read_data_as_plain_text(self):
        infile = StringIO(
            '<html><body>\n'
            'hello there<br>\n'
            'how are you\n'
            '</body></html>')
        expected = ['\n', 'hello there\n', 'how are you\n', '']
        self.assertEqual(list(notebook.read_data_as_plain_text(infile)),
                         expected)

        # </body> on same line as text
        infile = StringIO(
            '<html><body>\n'
            'hello there<br>\n'
            'how are you</body></html>')
        expected = ['\n', 'hello there\n', 'how are you']
        self.assertEqual(list(notebook.read_data_as_plain_text(infile)),
                         expected)

        # <body> on same line as text
        infile = StringIO(
            '<html><body>hello there<br>\n'
            'how are you\n'
            '</body></html>')
        expected = ['hello there\n', 'how are you\n', '']
        self.assertEqual(list(notebook.read_data_as_plain_text(infile)),
                         expected)

        # <body> and </body> on same line as text
        infile = StringIO(
            '<html><body>hello there</body></html>')
        expected = ['hello there']
        self.assertEqual(list(notebook.read_data_as_plain_text(infile)),
                         expected)

    def test_node_url(self):
        """Node URL API."""
        self.assertTrue(notebook.is_node_url(
            "nbk:///0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"))
        self.assertFalse(
            notebook.is_node_url("nbk://bad_url"))
        self.assertFalse(notebook.is_node_url(
            "http:///0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6"))

        host, nodeid = notebook.parse_node_url(
            "nbk:///0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6")
        self.assertEqual(host, "")
        self.assertEqual(nodeid, "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6")

        host, nodeid = notebook.parse_node_url(
            "nbk://host/0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6")
        self.assertEqual(host, "host")
        self.assertEqual(nodeid, "0841d4cc-2605-4fbb-9b3a-db5d4aeed7a6")

    def test_get_node_by_id(self):
        """Get a Node by its nodeid."""
        book = notebook.NoteBook()
        book.load(_notebook_file)

        node = book.get_node_by_id(self._pagex_nodeid)
        self.assertEqual(node.get_title(), 'Page X')
        book.close()

    def test_notebook_search_titles(self):
        """Search notebook titles."""
        book = notebook.NoteBook()
        book.load(_notebook_file)

        results = book.search_node_titles("Page X")
        self.assertTrue(self._pagex_nodeid in
                        (nodeid for nodeid, title in results))

        results = book.search_node_titles("Page")
        self.assertTrue(len(results) >= 7)

        book.close()

    def test_index_all(self):
        """Reindex all nodes in notebook."""
        book = notebook.NoteBook()
        book.load(_notebook_file)

        for node in book.index_all():
            print node

        book.close()

    def test_fts3(self):
        """Ensure full-text search is available."""
        con = sqlite.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE email USING fts3(content TEXT);")

        con.execute("INSERT INTO email VALUES ('hello there how are you');")
        con.execute("INSERT INTO email VALUES ('this is tastier');")

        self.assertTrue(len(list(
            con.execute("SELECT * FROM email WHERE content MATCH 'tast*';"))))

    def test_fulltext(self):
        """Full-text search notebook."""
        book = notebook.NoteBook()
        book.load(_notebook_file)

        results = list(book.search_node_contents('hello'))
        self.assertTrue(len(results) == 2)

        results = list(book.search_node_contents('world'))
        self.assertTrue(len(results) == 2)

        book.close()

    def test_notebook_threads(self):
        """Access a notebook in another thread"""
        test = self

        book = notebook.NoteBook()
        book.load(_notebook_file)

        class Task (threading.Thread):
            def run(self):
                try:
                    results = list(book.search_node_contents('world'))
                    test.assertTrue(len(results) == 2)
                except Exception as e:
                    traceback.print_exception(*sys.exc_info())
                    raise e

        task = Task()
        task.start()
        task.join()

        book.close()

    def test_notebook_threads2(self):
        """"""
        test = self
        error = [False]

        print
        book = notebook.NoteBook()
        book.load(_notebook_file)

        def process(book, name):
            for i in range(100):
                print i, name
                results = list(book.search_node_contents('world'))
                test.assertTrue(len(results) == 2)
                time.sleep(.001)

        class Task (threading.Thread):
            def run(self):
                try:
                    process(book, 'B')
                except Exception, e:
                    error[0] = True
                    traceback.print_exception(type(e), e, sys.exc_info()[2])
                    raise e

        task = Task()
        task.start()
        process(book, 'A')
        task.join()

        book.close()

        self.assertFalse(error[0])

    def _test_concurrent(self):
        """Open a notebook twice."""
        book1 = notebook.NoteBook()
        book1.load(_notebook_file)

        book2 = notebook.NoteBook()
        book2.load(_notebook_file)

        print list(book1.iter_attr())
        print list(book2.iter_attr())

        book1.close()
        book2.close()

    def test_create_unicode_node(self):
        """Create a node with a unicode title."""
        book = notebook.NoteBook()
        book.load(_notebook_file)
        notebook.new_page(book, u'Déjà vu')
        book.close()

    def test_notebook_move_deja_vu(self):
        """Move a unicode titled node."""
        book = notebook.NoteBook()
        book.load(_notebook_file)

        deja = notebook.new_page(book, u'Déjà vu again')
        nodex = book.get_node_by_id(self._pagex_nodeid)
        deja.move(nodex)

        # clean up.
        deja.delete()

        book.close()
