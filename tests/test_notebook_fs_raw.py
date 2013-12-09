
# python imports
import os
import uuid

# keepnote imports
from keepnote.notebook.connection import fs_raw

from .test_notebook_conn import TestConnBase
from . import make_clean_dir, TMP_DIR


class FSRaw (TestConnBase):

    def test_api(self):
        # initialize a notebook
        filename = TMP_DIR + '/notebook_fs_raw/n1'
        make_clean_dir(TMP_DIR + '/notebook_fs_raw')

        conn = fs_raw.NoteBookConnectionFSRaw()
        conn.connect(filename)
        self._test_api(conn)

        conn.close()

    def test_notebook(self):
        # initialize a notebook
        filename = TMP_DIR + '/notebook_fs_raw/n2'
        make_clean_dir(TMP_DIR + '/notebook_fs_raw')

        conn = fs_raw.NoteBookConnectionFSRaw()
        self._test_notebook(conn, filename)

        conn.close()

    def test_nodedirs_standard(self):
        """Basic NodeFSStandard API."""

        filename = TMP_DIR + '/notebook_fs_raw/nodedirs_standard'
        make_clean_dir(filename)

        nodedirs = fs_raw.NodeFSStandard(filename)

        # Create nodedirs.
        dir1 = nodedirs.create_nodedir('abcdefg')
        dir2 = nodedirs.create_nodedir('abcdefghij')
        dir3 = nodedirs.create_nodedir('1234567')
        dir4 = nodedirs.create_nodedir('1234568')

        self.assertTrue(os.path.exists(dir1))
        self.assertTrue(os.path.exists(dir2))
        self.assertTrue(os.path.exists(dir3))
        self.assertTrue(os.path.exists(dir4))

        # Test existence of nodedirs.
        self.assertTrue(nodedirs.has_nodedir('abcdefg'))
        self.assertFalse(nodedirs.has_nodedir('abcdefg_unknown'))

        # Delete nodedirs.
        nodedirs.delete_nodedir('1234568')
        self.assertFalse(os.path.exists(dir4))

        # Test short nodeids.
        dir_short = nodedirs.create_nodedir('ab')
        self.assertTrue(os.path.exists(dir_short))
        self.assertTrue(nodedirs.has_nodedir('ab'))
        nodedirs.delete_nodedir('ab')
        self.assertFalse(os.path.exists(dir_short))

        nodedirs.create_nodedir('ab')
        nodedirs.create_nodedir('ac')
        nodedirs.create_nodedir('a')

        # Test invalid nodeid lengths.
        self.assertRaises(Exception, lambda: nodedirs.create_nodedir(''))
        self.assertRaises(
            Exception, lambda: nodedirs.create_nodedir('x' * 256))

        # Test banned nodeids.
        self.assertRaises(Exception, lambda: nodedirs.create_nodedir('.'))
        self.assertRaises(Exception, lambda: nodedirs.create_nodedir('..'))

        # Test invalid characters.
        self.assertRaises(Exception, lambda: nodedirs.create_nodedir('ABC'))
        self.assertRaises(Exception, lambda: nodedirs.create_nodedir('abc+'))
        self.assertRaises(Exception, lambda:
                          nodedirs.create_nodedir('abc/aaa'))

        # Create nodedirs with dots.
        nodedirs.create_nodedir('...')
        nodedirs.create_nodedir('....')
        nodedirs.create_nodedir('ab.')
        nodedirs.create_nodedir('ab..')

        self.assertTrue(nodedirs.has_nodedir('ab.'))
        self.assertTrue(nodedirs.has_nodedir('ab..'))
        self.assertFalse(nodedirs.has_nodedir('ac.'))

        self.assertEqual(
            set(nodedirs.iter_nodeids()),
            set(['abcdefg', u'abcdefghij', u'1234567',
                 'ab', 'ac', 'a',
                 '...', '....', 'ab.', 'ab..']))

        nodedirs.close()

    def test_nodedirs(self):
        """Basic NodeFS API."""

        filename = TMP_DIR + '/notebook_fs_raw/nodedirs'
        make_clean_dir(filename)

        nodedirs = fs_raw.NodeFS(filename)

        # Create nodedirs.
        dir1 = nodedirs.create_nodedir('abcdefg')
        dir2 = nodedirs.create_nodedir('abcdefghij')
        dir3 = nodedirs.create_nodedir('1234567')
        dir4 = nodedirs.create_nodedir('1234568')

        self.assertTrue(os.path.exists(dir1))
        self.assertTrue(os.path.exists(dir2))
        self.assertTrue(os.path.exists(dir3))
        self.assertTrue(os.path.exists(dir4))

        # Test existence of nodedirs.
        self.assertTrue(nodedirs.has_nodedir('abcdefg'))
        self.assertFalse(nodedirs.has_nodedir('abcdefg_unknown'))

        # Delete nodedirs.
        nodedirs.delete_nodedir('1234568')
        self.assertFalse(os.path.exists(dir4))

        # Test short nodeids.
        dir_short = nodedirs.create_nodedir('ab')
        self.assertTrue(os.path.exists(dir_short))
        self.assertTrue(nodedirs.has_nodedir('ab'))
        nodedirs.delete_nodedir('ab')
        self.assertFalse(os.path.exists(dir_short))

        nodedirs.create_nodedir('ab')
        nodedirs.create_nodedir('ac')
        nodedirs.create_nodedir('a')

        # Test invalid nodeid lengths.
        self.assertRaises(Exception, lambda: nodedirs.create_nodedir(''))

        # Test nonstandard nodeids.
        nodedirs.create_nodedir('x' * 256)
        nodedirs.create_nodedir('.')
        nodedirs.create_nodedir('..')
        nodedirs.create_nodedir('ABC')
        nodedirs.create_nodedir('abc+')
        nodedirs.create_nodedir('abc/aaa')

        self.assertTrue(nodedirs.has_nodedir('ABC'))
        self.assertTrue(nodedirs.has_nodedir('abc+'))
        self.assertTrue(nodedirs.has_nodedir('abc/aaa'))

        # Create nodedirs with dots.
        nodedirs.create_nodedir('...')
        nodedirs.create_nodedir('....')
        nodedirs.create_nodedir('ab.')
        nodedirs.create_nodedir('ab..')

        self.assertTrue(nodedirs.has_nodedir('ab.'))
        self.assertTrue(nodedirs.has_nodedir('ab..'))
        self.assertFalse(nodedirs.has_nodedir('ac.'))

        self.assertEqual(
            set(nodedirs.iter_nodeids()),
            set(['abcdefg', u'abcdefghij', u'1234567',
                 'ab', 'ac', 'a',
                 '...', '....', 'ab.', 'ab..',
                 'x' * 256, '.', '..', 'ABC', 'abc+', 'abc/aaa']))

        nodedirs.delete_nodedir('ABC')
        self.assertEqual(
            set(nodedirs.iter_nodeids()),
            set(['abcdefg', u'abcdefghij', u'1234567',
                 'ab', 'ac', 'a',
                 '...', '....', 'ab.', 'ab..',
                 'x' * 256, '.', '..', 'abc+', 'abc/aaa']))

        nodedirs.close()

    def test_no_extra(self):
        """Ensure nodeid iteration occurs even when no small nodids exists."""

        filename = TMP_DIR + '/notebook_fs_raw/nodedirs_no_extra'
        make_clean_dir(filename)

        nodedirs = fs_raw.NodeFS(filename)
        nodedirs.create_nodedir('abcdefg')
        nodedirs.create_nodedir('abcdefghij')
        nodedirs.create_nodedir('1234567')

        self.assertEqual(
            set(nodedirs.iter_nodeids()),
            set(['abcdefg', u'abcdefghij', u'1234567']))

        nodedirs.close()

    def test_many_nodeids(self):

        filename = TMP_DIR + '/notebook_fs_raw/nodedirs_many'
        make_clean_dir(filename)

        nodedirs = fs_raw.NodeFS(filename)
        for i in xrange(1000):
            nodeid = str(uuid.uuid4())
            nodedirs.create_nodedir(nodeid)

        nodedirs.close()
