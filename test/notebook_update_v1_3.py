import os, shutil, unittest, traceback, sys


import keepnote.compat.notebook_v1 as oldnotebooklib
from keepnote import notebook as notebooklib
from keepnote.notebook import update



def mk_clean_dir(dirname):
    if os.path.exists(dirname):
        shutil.rmtree(dirname)
    os.makedirs(dirname)
    

class TestCaseNoteBookUpdate (unittest.TestCase):
    
    def setUp(self):      
        pass


    def _test1(self):
        """test notebook update from version 1 to 3"""

        old_notebook_filename = "test/data/notebook-v1"
        new_notebook_filename = "test/data/notebook-v3-update"
        new_version = 3

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

        def walk(node):
            attr = dict(list(node.iter_attr()))
            node.write_meta_data()

            try:
                node.read_meta_data()
            except:
                print "error reading node '%s'" % node.get_path()
                raise
            attr2 = dict(list(node.iter_attr()))

            self.assertEquals(attr, attr2)

            # recurse
            for child in node.get_children():
                walk(child)
        notebook = notebooklib.NoteBook()
        notebook.load(new_notebook_filename)
        walk(notebook)

        self.assert_(notebook._attr["title"] != "None")


    def test_gui(self):
        """test notebook update through gui"""

        old_notebook_filename = "test/data/notebook-v1"
        new_notebook_filename = "test/data/notebook-v3-update"
        new_version = 3

        # make copy of old notebook
        if os.path.exists(new_notebook_filename):
            shutil.rmtree(new_notebook_filename)
        shutil.copytree(old_notebook_filename,
                        new_notebook_filename)

        self.assertEquals(
            os.system("bin/keepnote --newproc %s" % new_notebook_filename), 0)


        
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseNoteBookUpdate)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)

