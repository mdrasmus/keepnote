
# python imports
from StringIO import StringIO
import sys
import unittest

# keepnote imports
from keepnote import notebook
import keepnote.notebook.connection as connlib
from keepnote.notebook.connection import FileError

from . import TMP_DIR

_tmpdir = TMP_DIR + '/notebook_conn/'


def display_notebook(node, depth=0, out=sys.stdout):
    print >>out, " " * depth + node.get_attr("title")
    for child in node.get_children():
        display_notebook(child, depth+2, out)


class TestConnBase (unittest.TestCase):

    def _test_api(self, conn):
        self._test_nodes(conn)
        self._test_files(conn)

    def _test_nodes(self, conn):

        self._test_create_read_node(conn)
        self._test_update_node(conn)
        self._test_delete_node(conn)
        self._test_unknown_node(conn)

    def _test_create_read_node(self, conn):

        attrs = [
            # Basic types.
            {
                'key1': 1,
                'key2': 2.0,
                'key3': '3',
                'key4': True,
                'key5': None,
            },

            # Empty attributes.
            {},

            # Complex attributes.
            {
                'a list': [1, 2, 'x'],
                'a dict': {
                    'a': 1,
                    'bb': 2,
                    'cc': 4.0,
                },
            },
        ]

        for i, attr in enumerate(attrs):
            nodeid = 'create%d' % i
            conn.create_node(nodeid, attr)

            # Node should now exist.
            self.assertTrue(conn.has_node(nodeid))

            # Read a node back.  It should match the stored data.
            attr2 = conn.read_node(nodeid)
            self.assertEqual(attr, attr2)

        # Double create should fail.
        conn.create_node('double_create', {})
        self.assertRaises(connlib.NodeExists,
                          lambda: conn.create_node('double_create', {}))

    def _test_update_node(self, conn):
        # Create node.
        attr = {
            'key1': 1,
            'key2': 2.0,
            'key3': '3',
            'key4': True,
            'key5': None,
        }
        conn.create_node('node2', attr)

        # Update a node.
        attr['key2'] = 5.0
        conn.update_node('node2', attr)

        # Read a node back.  It should match the stored data.
        attr2 = conn.read_node('node2')
        self.assertEqual(attr, attr2)

    def _test_delete_node(self, conn):
        # Create node.
        attr = {
            'key1': 1,
            'key2': 2.0,
            'key3': '3',
            'key4': True,
            'key5': None,
        }
        conn.create_node('node3', attr)
        self.assertTrue(conn.has_node('node3'))

        # Delete node.
        conn.delete_node('node3')
        self.assertFalse(conn.has_node('node3'))
        self.assertRaises(connlib.UnknownNode,
                          lambda: conn.read_node('node3'))

    def _test_unknown_node(self, conn):

        self.assertRaises(connlib.UnknownNode, lambda:
                          conn.read_node('unknown_node'))
        self.assertRaises(connlib.UnknownNode,
                          lambda: conn.update_node('unknown_node', {}))
        self.assertRaises(connlib.UnknownNode,
                          lambda: conn.delete_node('unknown_node'))

    def _test_files(self, conn):

        # Create empty node.
        if conn.has_node('node1'):
            conn.delete_node('node1')
        conn.create_node('node1', {})

        # Write file.
        data = 'hello world'
        with conn.open_file('node1', 'file1', 'w') as out:
            out.write(data)

        # Read file.
        with conn.open_file('node1', 'file1') as infile:
            self.assertEqual(infile.read(), data)

        # Write file inside directory.
        data2 = 'another hello world'
        with conn.open_file('node1', 'dir1/file1', 'w') as out:
            out.write(data2)

        # Read file inside a directory.
        with conn.open_file('node1', 'dir1/file1') as infile:
            self.assertEqual(infile.read(), data2)

        # Delete a file.
        conn.delete_file('node1', 'dir1/file1')
        self.assertFalse(conn.has_file('node1', 'dir1/file1'))

        # Delete a directory.
        self.assertTrue(conn.has_file('node1', 'dir1/'))
        conn.delete_file('node1', 'dir1/')
        self.assertFalse(conn.has_file('node1', 'dir1/'))

        # Delete a non-empty directory.
        conn.open_file('node1', 'dir3/dir/file1', 'w').close()
        self.assertTrue(conn.has_file('node1', 'dir3/dir/file1'))
        conn.delete_file('node1', 'dir3/')
        self.assertFalse(conn.has_file('node1', 'dir3/'))

        # Create a directory.
        conn.create_dir('node1', 'new dir/')

        # Require trailing / for directories.
        # Do not allow trailing / for files.
        self.assertRaises(FileError, lambda:
                          conn.create_dir('node1', 'bad dir'))
        self.assertRaises(FileError, lambda:
                          conn.open_file('node1', 'bad file/', 'w'))
        self.assertRaises(FileError, lambda:
                          conn.create_dir('node1', 'bad dir'))
        self.assertRaises(FileError, lambda:
                          list(conn.list_dir('node1', 'file1')))

        # Should not delete file because its given as a dir.
        conn.delete_file('node1', 'file1/')
        self.assertTrue(conn.has_file('node1', 'file1'))

        # Should not delete dir, becuase its given as a file.
        conn.delete_file('node1', 'new dir')
        self.assertTrue(conn.has_file('node1', 'new dir/'))

        # Rename file.
        conn.move_file('node1', 'file1', 'node1', 'file2')
        self.assertFalse(conn.has_file('node1', 'file1'))
        self.assertTrue(conn.has_file('node1', 'file2'))

        # Move a file.
        if conn.has_node('node2'):
            conn.delete_node('node2')
        conn.create_node('node2', {})
        conn.move_file('node1', 'file2', 'node2', 'file2')
        self.assertFalse(conn.has_file('node1', 'file2'))
        self.assertTrue(conn.has_file('node2', 'file2'))

        # Copy a file.
        conn.copy_file('node2', 'file2', 'node1', 'copied-file')
        self.assertTrue(conn.has_file('node2', 'file2'))
        self.assertTrue(conn.has_file('node1', 'copied-file'))
        self.assertEqual(conn.open_file('node1', 'copied-file').read(),
                         data)

        # Ensure files aren't interpreted as children files.
        # Create a file that conflicts with a child node directory.
        conn.create_node('node3', {})
        data2 = 'another hello world'
        conn.create_node('dir2', {
            'nodeid': 'dir2',
            'title': 'dir2',
            'parentids': ['node3']})

        with conn.open_file('node3', 'dir2/file1', 'w') as out:
            out.write(data2)

        with conn.open_file('node3', 'dir2/file1') as infile:
            self.assertEqual(infile.read(), data2)

        self.assertTrue(conn.has_file('node3', 'dir2/file1'))
        # TODO: fix this bug for FS.
        #self.assertFalse(conn.has_file('dir2', 'file1'))

        # listdir should return full file paths.
        conn.open_file('node3', 'dir2/file2', 'w').close()
        conn.create_dir('node3', 'dir2/dir3/')
        conn.open_file('node3', 'dir2/dir3/file1', 'w').close()
        self.assertEqual(
            set(conn.list_dir('node3', 'dir2/')),
            set(['dir2/file1', 'dir2/file2', 'dir2/dir3/']))

    def _test_notebook(self, conn, filename):

        # initialize a notebook
        book1 = notebook.NoteBook()
        book1.create(filename, conn)
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


class TestConn (unittest.TestCase):

    def test_basename(self):

        """
        Return the last component of a filename

        aaa/bbb   =>  bbb
        aaa/bbb/  =>  bbb
        aaa/      =>  aaa
        aaa       =>  aaa
        ''        =>  ''
        /         =>  ''
        """
        self.assertEqual(connlib.path_basename("aaa/b/ccc"), "ccc")
        self.assertEqual(connlib.path_basename("aaa/b/ccc/"), "ccc")
        self.assertEqual(connlib.path_basename("aaa/bbb"), "bbb")
        self.assertEqual(connlib.path_basename("aaa/bbb/"), "bbb")
        self.assertEqual(connlib.path_basename("aaa"), "aaa")
        self.assertEqual(connlib.path_basename("aaa/"), "aaa")
        self.assertEqual(connlib.path_basename(""), "")
        self.assertEqual(connlib.path_basename("/"), "")
