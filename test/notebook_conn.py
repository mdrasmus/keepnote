




# python imports
import os, sys, shutil

from testing import *

# keepnote imports
from keepnote import notebook, safefile
import keepnote.notebook.connection as connlib


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


        
if __name__ == "__main__":
    test_main()

