import os
import unittest

# keepnote imports
import keepnote
from keepnote import extension

from . import clean_dir, DATA_DIR, TMP_DIR


# paths
_tmppath = os.path.join(TMP_DIR, 'extension')
_home = os.path.join(_tmppath, 'home')
_extension_file = os.path.join(DATA_DIR, 'test_extension.kne')
_pref_dir = os.path.join(_home, '.config', 'keepnote')


class ExtensionInstall (unittest.TestCase):

    def test_extension_api(self):
        """Extension API"""

        # Initilize app.
        clean_dir(_tmppath)
        app = keepnote.KeepNote(pref_dir=_pref_dir)
        app.init()

        # Ensure extension install file can be detected as one.
        self.assertTrue(extension.is_extension_install_file(_extension_file))

        # Install extension using API.
        [ext] = app.install_extension(_extension_file)
        self.assertTrue(os.path.exists(
            _pref_dir + '/extensions/test_extension/info.xml'))

        # Ensure extension is installed.
        self.assertTrue(
            app.get_extension('test_extension').key == 'test_extension')
        self.assertTrue('test_extension' in app.get_installed_extensions())

        # Extension should be auto-imported.
        self.assertTrue(
            'test_extension' in (
                ext.key for ext in app.get_imported_extensions()))

        # Extension should be auto-enabled.
        self.assertTrue(
            'test_extension' in (
                ext.key for ext in app.get_enabled_extensions()))

        # Check basic extension information is available.
        self.assertTrue(app.get_extension_base_dir('test_extension'))
        self.assertTrue(app.get_extension_data_dir('test_extension'))

        # Disable extension.
        ext.enable(False)
        self.assertTrue(
            'test_extension' not in (
                ext.key for ext in app.get_enabled_extensions()))

        # Uninstall extension using API.
        self.assertTrue(app.can_uninstall(ext))
        app.uninstall_extension('test_extension')
        self.assertFalse(os.path.exists(
            _pref_dir + '/extensions/test_extension/info.xml'))

    def test_disabled_extensions(self):
        """Extension disabled in preferences should not be enabled."""

        # Initilize app.
        clean_dir(_tmppath)
        app = keepnote.KeepNote(pref_dir=_pref_dir)
        app.init()

        # Disable extension.
        ext = next(ext for ext in app.get_enabled_extensions()
                   if ext.key != 'keepnote')
        ext.enable(False)
        ext_key = ext.key

        # Reload app.
        app.save()
        app = keepnote.KeepNote(pref_dir=_pref_dir)
        app.init()

        # Extension should still be disabled.
        self.assertFalse(app.get_extension(ext_key).is_enabled())

    def test_install_twice(self):
        """Installing an extension twice should fail gracefully."""

        # Initilize app.
        clean_dir(_tmppath)
        app = keepnote.KeepNote(pref_dir=_pref_dir)
        app.init()

        # Install extension twice.
        [ext] = app.install_extension(_extension_file)
        self.assertTrue(app.install_extension(_extension_file) == [])

    def test_install_prog(self):
        """Extension install using program from command-line."""
        clean_dir(_tmppath)
        os.system(
            "HOME=%s bin/keepnote --no-gui -c install '%s'"
            % (_home, _extension_file))
        self.assertTrue(os.path.exists(
            _pref_dir + '/extensions/test_extension/info.xml'))
