
# python imports
import os
import unittest

# keepnote imports
from keepnote import PROGRAM_VERSION_TEXT

from . import TMP_DIR, SRC_DIR, make_clean_dir


class Install (unittest.TestCase):

    def system(self, cmd, err_code=0):
        print cmd
        self.assertEqual(os.system(cmd), err_code)

    def test_distutil_sdist(self):
        """Test distutil install"""

        pkg = "keepnote-%s" % PROGRAM_VERSION_TEXT
        sdist = SRC_DIR + "/dist/%s.tar.gz" % pkg
        install_dir = TMP_DIR + "/install/distutil"
        home_dir = TMP_DIR + "/install/home"

        if not os.path.exists(sdist):
            raise OSError('Must build install package to test: %s' % sdist)

        make_clean_dir(install_dir)
        make_clean_dir(home_dir)

        self.system("tar zxv -C %s -f %s" % (install_dir, sdist))

        self.system("/usr/bin/python %s/%s/setup.py install --home=%s" %
                    (install_dir, pkg, install_dir))

        # To allow gui to run.
        self.system("cp ~/.Xauthority %s" % home_dir)

        self.system("HOME=%s; PYTHONPATH=%s/lib/python; "
                    "python %s/bin/keepnote --no-gui" %
                    (home_dir, install_dir, install_dir))
