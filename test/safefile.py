import os, shutil, unittest

from takenote.safefile import SafeFile


def mk_clean_dir(dirname):
    if os.path.exists(dirname):
        shutil.rmtree(dirname)
    os.makedirs(dirname)
    

class TestCaseSafeFile (unittest.TestCase):
    
    def setUp(self):      

        for f in os.listdir("test/tmp"):
            if f.startswith("safefile"):
                os.remove(os.path.join("test/tmp", f))


    def test1(self):
        """test successful write"""

        filename = "test/tmp/safefile"

        out = SafeFile(filename, "w")

        out.write("hello\n")
        out.write("there")
        out.close()

        self.assertEquals(SafeFile(filename).read(), "hello\nthere")        
        self.assertEquals(os.path.exists(out.get_tempfile()), False)


    def test2(self):
        """test unsuccessful write"""

        filename = "test/tmp/safefile"

        # make file
        self.test1()

        try:
            out = SafeFile(filename, "w")

            out.write("hello2\n")
            raise Exception("oops")
            out.write("there2")
            out.close()
        except:
            pass

        self.assertEquals(SafeFile(filename).read(), "hello\nthere")        
        self.assertEquals(os.path.exists(out.get_tempfile()), True)
        
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseSafeFile)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)

