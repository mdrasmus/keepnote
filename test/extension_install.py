import os, shutil, unittest, thread, threading, traceback, sys

# keepnote imports
import keepnote
from keepnote import notebook



class ExtensionInstall (unittest.TestCase):
    
    def test_install_gui(self):
        """Simple extension install"""

        # remove old extension
        os.system("rm -rf ~/.config/keepnote/extensions/test_extension")
        os.system("bin/keepnote --newproc test/data/test_extension.kne")

        # remove extension
        os.system("rm -rf ~/.config/keepnote/extensions/test_extension")


    def _test_double_install_gui(self):        
        """Test double install"""

        # remove old extension
        os.system("rm -rf ~/.config/keepnote/extensions/test_extension")
        os.system("bin/keepnote --newproc test/data/test_extension.kne")
        os.system("bin/keepnote --newproc test/data/test_extension.kne")

        # remove extension
        os.system("rm -rf ~/.config/keepnote/extensions/test_extension")


        
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    ExtensionInstall)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite)

