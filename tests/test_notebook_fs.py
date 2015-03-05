
# python imports
import os

# keepnote imports
from keepnote.notebook import NOTEBOOK_FORMAT_VERSION
import keepnote.notebook.connection as connlib
from keepnote.notebook.connection import fs

from .test_notebook_conn import TestConnBase
from . import clean_dir
from . import TMP_DIR

_tmpdir = TMP_DIR + '/notebook_conn/'


class TestConnFS (TestConnBase):

    def test_api(self):
        """Test NoteBookConnectionFS file API."""
        notebook_file = _tmpdir + '/notebook_files'
        clean_dir(notebook_file)

        # Start connection.
        conn = fs.BaseNoteBookConnectionFS()
        conn.connect(notebook_file)

        # Create root node.
        attr = {
            # Required attributes.
            'nodeid': 'root',
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
        conn.create_node('root', attr)
        self._test_api(conn)

    def test_fs_orphan(self):
        """Test orphan node directory names"""
        self.assertEqual(fs.get_orphandir('path', 'abcdefh'),
                         'path/__NOTEBOOK__/orphans/ab/cdefh')
        self.assertEqual(fs.get_orphandir('path', 'ab'),
                         'path/__NOTEBOOK__/orphans/ab')
        self.assertEqual(fs.get_orphandir('path', 'a'),
                         'path/__NOTEBOOK__/orphans/a')

    def test_fs_schema(self):
        """Test NoteBook-specific schema behavior."""
        notebook_file = _tmpdir + '/notebook_nodes'
        clean_dir(notebook_file)

        # Start connection.
        conn = fs.NoteBookConnectionFS()
        conn.connect(notebook_file)

        # Create root node with no attributes given.
        nodeid = conn.create_node(None, {})
        attr = conn.read_node(nodeid)

        # Assert that default keys are added.
        expected_keys = ['nodeid', 'parentids', 'childrenids', 'version']
        for key in expected_keys:
            self.assertIn(key, attr)

        # New root node should have no parents or children.
        self.assertEquals(attr['parentids'], [])
        self.assertEquals(attr['childrenids'], [])

        # Updating a node should enforce schema required keys.
        conn.update_node(nodeid, {})
        attr2 = conn.read_node(nodeid)
        self.assertEqual(attr, attr2)

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
        self.assertRaises(connlib.UnknownNode,
                          lambda: conn.read_node('n'))

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
