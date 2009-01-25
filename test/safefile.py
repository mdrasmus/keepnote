import os, shutil, unittest, codecs


from keepnote import safefile


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

        out = safefile.open(filename, "w", codec="utf-8")
        tmp = out.get_tempfile()
        
        out.write(u"\u2022 hello\n")
        out.write(u"there")
        out.close()

        self.assertEquals(safefile.open(filename, codec="utf-8").read(),
                          u"\u2022 hello\nthere")
        self.assertEquals(os.path.exists(tmp), False)


    def test2(self):
        """test unsuccessful write"""

        filename = "test/tmp/safefile"

        # make file
        self.test1()

        try:
            out = safefile.open(filename, "w")

            out.write("hello2\n")
            raise Exception("oops")
            out.write("there2")
            out.close()
        except:
            pass

        self.assertEquals(safefile.open(filename, codec="utf-8").read(),
                          u"\u2022 hello\nthere")
        self.assertEquals(os.path.exists(out.get_tempfile()), True)


    def test3(self):

        filename = "test/tmp/safefile"

        out = safefile.open(filename, "w", codec="utf-8")
        out.write(u"\u2022 hello\nthere\nagain\n")
        out.close()

        lines = safefile.open(filename, codec="utf-8").readlines()

        self.assertEquals(lines, [u"\u2022 hello\n",
                                  u"there\n",
                                  u"again\n"])

        lines = list(safefile.open(filename, codec="utf-8"))

        self.assertEquals(lines, [u"\u2022 hello\n",
                                  u"there\n",
                                  u"again\n"])

    def test4(self):

        filename = "test/tmp/safefile"
        
        out = safefile.open(filename, "w", codec="utf-8")

        out.writelines([u"\u2022 hello\n",
                        u"there\n",
                        u"again\n"])
        out.close()

        lines = safefile.open(filename, codec="utf-8").readlines()

        self.assertEquals(lines, [u"\u2022 hello\n",
                                  u"there\n",
                                  u"again\n"])


        
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseSafeFile)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)

