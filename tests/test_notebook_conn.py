
# python imports
import os
import unittest

# keepnote imports
from keepnote.notebook import NOTEBOOK_FORMAT_VERSION
import keepnote.notebook.connection as connlib
from keepnote.notebook.connection import fs

from . import clean_dir, TMP_DIR

_tmpdir = TMP_DIR + '/notebook_conn/'


class ConnBase (unittest.TestCase):

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

    def _test_unknown_node(self, conn):

        self.assertRaises(connlib.UnknownNode, lambda:
                          conn.read_node('unknown_node'))
        self.assertRaises(connlib.UnknownNode,
                          lambda: conn.update_node('unknown_node', {}))
        self.assertRaises(connlib.UnknownNode,
                          lambda: conn.delete_node('unknown_node'))


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
        self.assertRaises(fs.FileError, lambda:
                          conn.create_dir('node1', 'bad dir'))
        self.assertRaises(fs.FileError, lambda:
                          conn.open_file('node1', 'bad file/', 'w'))

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


class Conn (unittest.TestCase):

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

class ConnFS (ConnBase):

    def test_fs_orphan(self):
        """Test orphan node directory names"""
        self.assertEqual(fs.get_orphandir('path', 'abcdefh'),
                         'path/__NOTEBOOK__/orphans/ab/cdefh')
        self.assertEqual(fs.get_orphandir('path', 'ab'),
                         'path/__NOTEBOOK__/orphans/ab')
        self.assertEqual(fs.get_orphandir('path', 'a'),
                         'path/__NOTEBOOK__/orphans/a')

    def test_fs_nodes(self):
        """Test NoteBookConnectionFS node API."""
        notebook_file = _tmpdir + '/notebook_nodes'
        clean_dir(notebook_file)

        # Start connection.
        conn = fs.NoteBookConnectionFS()
        conn.connect(notebook_file)

        # Create root node.
        attr = {
            # Required attributes.
            'nodeid': 'node1',
            'version': NOTEBOOK_FORMAT_VERSION,
            'parentids': [],
            'childrenids': [],

            # Custom attributes.
            'key1': 1,
            'key2': 2.0,
            'key3': '3',
            'key4': True,
            'key5': None,
        }
        conn.create_node('node1', attr)

        self.assertTrue(
            os.path.exists(notebook_file + '/node.xml'))
        self.assertTrue(conn.has_node('node1'))
        self.assertEqual(conn.get_rootid(), 'node1')

        # Read a node back.  It should match the stored data.
        attr2 = conn.read_node('node1')
        self.assertEqual(attr, attr2)

        # Update a node.
        attr2['key2'] = 5.0
        conn.update_node('node1', attr2)

        # Read a node back.  It should match the stored data.
        attr3 = conn.read_node('node1')
        self.assertEqual(attr2, attr3)

        # Create another node.
        attr = {
            # Required attributes.
            'nodeid': 'node2',
            'version': NOTEBOOK_FORMAT_VERSION,
            'parentids': [],

            # Custom attributes.
            'key1': 1,
            'key2': 2.0,
            'key3': '3',
            'key4': True,
            'key5': None,
        }
        conn.create_node('node2', attr)
        attr2 = conn.read_node('node2')
        self.assertEqual(attr, attr2)

        # Create another node.
        attr = {
            # Required attributes.
            'nodeid': 'n',
            'version': NOTEBOOK_FORMAT_VERSION,
            'parentids': [],

            # Custom attributes.
            'key1': 1,
            'key2': 2.0,
            'key3': '3',
            'key4': True,
            'key5': None,
        }
        conn.create_node('n', attr)
        attr2 = conn.read_node('n')
        self.assertEqual(attr, attr2)

        # Delete node.
        conn.delete_node('n')
        self.assertFalse(conn.has_node('n'))

        def func():
            attr2 = conn.read_node('n')

        self.assertRaises(connlib.UnknownNode, func)

        # Create child node.
        attr = {
            # Required attributes.
            'nodeid': 'node1_child',
            'version': NOTEBOOK_FORMAT_VERSION,
            'parentids': ['node1'],

            # Custom attributes.
            'key1': 1,
        }
        conn.create_node('node1_child', attr)
        self.assertTrue(
            os.path.exists(notebook_file + '/new page/node.xml'))

        # Create grandchild node.
        # Use title to set directory name.
        attr = {
            # Required attributes.
            'nodeid': 'node1_grandchild',
            'version': NOTEBOOK_FORMAT_VERSION,
            'parentids': ['node1_child'],
            'title': 'Node1 Grandchild',

            # Custom attributes.
            'key1': 1,
        }
        conn.create_node('node1_grandchild', attr)
        self.assertTrue(
            os.path.exists(notebook_file +
                           '/new page/node1 grandchild/node.xml'))

        # Clean up.
        conn.close()

    def test_fs_files(self):
        """Test NoteBookConnectionFS file API."""
        notebook_file = _tmpdir + '/notebook_files'
        clean_dir(notebook_file)

        # Start connection.
        conn = fs.NoteBookConnectionFS()
        conn.connect(notebook_file)

        # Create root node.
        attr = {
            # Required attributes.
            'nodeid': 'node1',
            'version': NOTEBOOK_FORMAT_VERSION,
            'parentids': [],
            'childrenids': [],

            # Custom attributes.
            'key1': 1,
            'key2': 2.0,
            'key3': '3',
            'key4': True,
            'key5': None,
        }
        conn.create_node('node1', attr)

        # Create file.
        data = 'hello world'
        with conn.open_file('node1', 'file1', 'w') as out:
            out.write(data)
        os.path.exists(notebook_file + '/file1')

        with conn.open_file('node1', 'file1') as infile:
            self.assertEqual(infile.read(), data)

        # Create file.
        data2 = 'another hello world'
        with conn.open_file('node1', 'dir1/file1', 'w') as out:
            out.write(data2)
        os.path.exists(notebook_file + '/dir1/file1')

        with conn.open_file('node1', 'dir1/file1') as infile:
            self.assertEqual(infile.read(), data2)

        # Create a file that conflicts with a child node directory.
        data2 = 'another hello world'
        conn.create_node('dir2', {
            'nodeid': 'dir2',
            'title': 'dir2',
            'parentids': ['node1']})

        with conn.open_file('node1', 'dir2/file1', 'w') as out:
            out.write(data2)
        os.path.exists(notebook_file + '/dir2/file1')

        with conn.open_file('node1', 'dir2/file1') as infile:
            self.assertEqual(infile.read(), data2)

        self.assertTrue(conn.has_file('node1', 'dir2/file1'))

        conn.open_file('node1', 'dir2/file2', 'w').close()
        conn.create_dir('node1', 'dir2/dir3/')
        self.assertEqual(
            set(conn.list_dir('node1', 'dir2')),
            set(['file1', 'file2', 'dir3/']))

        # TODO: fix this bug.
        #self.assertFalse(conn.has_file('dir2', 'file1'))

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
        self.assertRaises(fs.FileError, lambda:
                          conn.create_dir('node1', 'bad dir'))
        self.assertRaises(fs.FileError, lambda:
                          conn.open_file('node1', 'bad file/', 'w'))

        # Rename file.
        conn.move_file('node1', 'file1', 'node1', 'file2')
        self.assertFalse(conn.has_file('node1', 'file1'))
        self.assertTrue(conn.has_file('node1', 'file2'))

        # Move a file.
        conn.create_node('node2', {
            'nodeid': 'node2',
            'parentids': ['node1'],
            'title': 'node2',
        })
        conn.move_file('node1', 'file2', 'node2', 'file2')
        self.assertFalse(conn.has_file('node1', 'file2'))
        self.assertTrue(conn.has_file('node2', 'file2'))

        # Copy a file.
        conn.copy_file('node2', 'file2', 'node1', 'copied-file')
        self.assertTrue(conn.has_file('node2', 'file2'))
        self.assertTrue(conn.has_file('node1', 'copied-file'))
        self.assertEqual(conn.open_file('node1', 'copied-file').read(),
                         data)
