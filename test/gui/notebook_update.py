
from test.testing import *
import os, shutil, unittest, traceback, sys


import keepnote.compat.notebook_v1 as oldnotebooklib
from keepnote.compat import notebook_update_v5_6
from keepnote import notebook as notebooklib
from keepnote.notebook import update
import keepnote


class Update (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_gui(self):
        """test notebook update through gui"""

        new_version = notebooklib.NOTEBOOK_FORMAT_VERSION
        old_notebook_filename = "test/data/notebook-v3"
        new_notebook_filename = "test/data/notebook-v%d-update" % new_version
        

        # make copy of old notebook
        if os.path.exists(new_notebook_filename):
            shutil.rmtree(new_notebook_filename)
        shutil.copytree(old_notebook_filename,
                        new_notebook_filename)

        self.assertEquals(
            os.system("bin/keepnote --newproc %s" % new_notebook_filename), 0)


if __name__ == "__main__":
    test_main()

