import os, shutil, unittest


from takenote import notebook as notebooklib
from takenote import notebook_update



def mk_clean_dir(dirname):
    if os.path.exists(dirname):
        shutil.rmtree(dirname)
    os.makedirs(dirname)
    

class TestCaseNoteBookUpdate (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test1(self):
        """test notebook update from version 1 to 2"""

        old_notebook_filename = "test/data/notebook-v1"
        new_notebook_filename = "test/data/notebook-v2-update"
        new_version = 2

        # make copy of old notebook
        if os.path.exists(new_notebook_filename):
            shutil.rmtree(new_notebook_filename)
        shutil.copytree(old_notebook_filename,
                        new_notebook_filename)

        # update (in place) the copy
        notebook_update.update_notebook(new_notebook_filename, new_version)

        def walk(node):
            attr = dict(list(node.iter_attr()))
            node.write_meta_data()
            node.read_meta_data()
            attr2 = dict(list(node.iter_attr()))

            self.assertEquals(attr, attr2)

            # recurse
            for child in node.get_children():
                walk(child)
        notebook = notebooklib.NoteBook()
        notebook.load(new_notebook_filename)
        walk(notebook)


    def test_gui(self):
        """test notebook update through gui"""

        old_notebook_filename = "test/data/notebook-v1"
        new_notebook_filename = "test/data/notebook-v2-update"
        new_version = 2

        # make copy of old notebook
        if os.path.exists(new_notebook_filename):
            shutil.rmtree(new_notebook_filename)
        shutil.copytree(old_notebook_filename,
                        new_notebook_filename)

        self.assertEquals(
            os.system("bin/takenote %s" % new_notebook_filename), 0)


        
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseNoteBookUpdate)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)

