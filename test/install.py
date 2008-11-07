import os, shutil, unittest


def mk_clean_dir(dirname):
    if os.path.exists(dirname):
        shutil.rmtree(dirname)
    os.makedirs(dirname)
    

class TestCaseInstall (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_distutil(self):
        """Test distutil install"""

        install_dir = "test/tmp/distutil"
        home_dir = "test/tmp/home"
        
        mk_clean_dir(install_dir)
        mk_clean_dir(home_dir)
        
        self.assertEquals(
            os.system("python setup.py install --prefix=%s" % install_dir),
            0)

        self.assertEquals(
            os.system("HOME=%s %s/bin/takenote --no-default" %
                      (home_dir, install_dir)),
            0)

        
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseInstall)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)

