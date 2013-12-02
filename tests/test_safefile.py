import os
import unittest

from keepnote import safefile

from . import make_clean_dir, TMP_DIR


_tmpdir = os.path.join(TMP_DIR, 'safefile')


class TestCaseSafeFile (unittest.TestCase):

    def setUp(self):
        make_clean_dir(_tmpdir)

    def test1(self):
        """test successful write"""

        filename = _tmpdir + "/safefile"

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

        filename = _tmpdir + "/safefile"

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

        filename = _tmpdir + "/safefile"

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

        filename = _tmpdir + "/safefile"

        out = safefile.open(filename, "w", codec="utf-8")

        out.writelines([u"\u2022 hello\n",
                        u"there\n",
                        u"again\n"])
        out.close()

        lines = safefile.open(filename, codec="utf-8").readlines()

        self.assertEquals(lines, [u"\u2022 hello\n",
                                  u"there\n",
                                  u"again\n"])
