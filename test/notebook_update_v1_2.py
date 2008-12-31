import os, shutil, unittest


from takenote import notebook as notebooklib


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

        if os.path.exists(new_notebook_filename):
            shutil.rmtree(new_notebook_filename)
        shutil.copytree(old_notebook_filename,
                        new_notebook_filename)

        notebooklib.update_notebook(new_notebook_filename,
                                    2)
        

        
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseNoteBookUpdate)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)

