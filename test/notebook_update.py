
from testing import *
import os, shutil, unittest, traceback, sys


import keepnote.compat.notebook_v1 as oldnotebooklib
from keepnote.compat import notebook_update_v5_6
from keepnote import notebook as notebooklib
from keepnote.notebook import update
import keepnote


class Update (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test1(self):
        """test notebook update from version 1 to present"""

        new_version = notebooklib.NOTEBOOK_FORMAT_VERSION
        old_notebook_filename = "test/data/notebook-v1"
        new_notebook_filename = ("test/tmp/notebook-v%d-update" % new_version)

        # make copy of old notebook
        if os.path.exists(new_notebook_filename):
            shutil.rmtree(new_notebook_filename)

        print "preparing test..."
        shutil.copytree(old_notebook_filename,
                        new_notebook_filename)

        # test copy
        notebook = oldnotebooklib.NoteBook()
        notebook.load(new_notebook_filename)
        print notebook._attr

        # update (in place) the copy
        update.update_notebook(new_notebook_filename, new_version,
                               verify=False)

        self.assert_(notebook._attr["title"] != "None")


    def test_v5_6(self):
        
        # initialize two notebooks
        make_clean_dir("test/tmp/notebook_update")

        shutil.copytree("test/data/notebook-v5",
                        "test/tmp/notebook_update/n1")
        notebook_update_v5_6.update(u"test/tmp/notebook_update/n1")


    def test_v4_5(self):
        
        # initialize two notebooks
        make_clean_dir("test/tmp/notebook_update")

        shutil.copytree("test/data/notebook-v4",
                        "test/tmp/notebook_update/n1")
        update.update_notebook(u"test/tmp/notebook_update/n1", 5)


    def test_v3_6(self):
        
        # initialize two notebooks
        make_clean_dir("test/tmp/notebook_update")

        shutil.copytree("test/data/notebook-v3",
                        "test/tmp/notebook_update/n1")
        update.update_notebook(u"test/tmp/notebook_update/n1", 6)


if __name__ == "__main__":
    test_main()

