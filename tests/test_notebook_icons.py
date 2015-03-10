import os
import shutil
import unittest

# keepnote imports
from keepnote import notebook

from . import make_clean_dir
from . import TMP_DIR


# root path for test data
_datapath = os.path.join(TMP_DIR, 'notebook_icons')


class Tests (unittest.TestCase):
    def setUp(self):
        # Initialize a notebook
        make_clean_dir(_datapath)
        self.filename = os.path.join(_datapath, 'filename')
        shutil.copytree("tests/data/notebook-v6", self.filename)

    def test_notebook_read_icons(self):
        """
        Test whether icon preferences are stored correctly.
        """
        # Set quick icons.
        book = notebook.NoteBook()
        book.load(self.filename)
        book.pref.set_quick_pick_icons(["x.png"])
        book.set_preferences_dirty()
        book.save()

        # Assert that we can read them.
        self.assertEqual(book.pref.get_quick_pick_icons(), ["x.png"])
        book.close()

        book.load(self.filename)
        self.assertEqual(book.pref.get_quick_pick_icons(), ["x.png"])
        book.close()

    def test_install_icon(self):
        """
        Test whether icon installing works correctly.
        """
        book = notebook.NoteBook()
        book.load(self.filename)

        files_before = sorted(
            os.listdir(self.filename + "/__NOTEBOOK__/icons"))
        self.assertEqual(files_before, ['zip-2.png', 'zip.png'])

        # Install the same icon twice.
        book.install_icon("share/icons/gnome/16x16/mimetypes/zip.png")
        book.install_icon("share/icons/gnome/16x16/mimetypes/zip.png")

        book.install_icons(
            "keepnote/images/node_icons/folder-orange.png",
            "keepnote/images/node_icons/folder-orange-open.png")
        book.install_icons(
            "keepnote/images/node_icons/folder-orange.png",
            "keepnote/images/node_icons/folder-orange-open.png")

        book.save()

        # Check that unique names were given.
        files_after = sorted(os.listdir(self.filename + "/__NOTEBOOK__/icons"))
        self.assertEqual(
            files_after,
            ['folder-orange-2-open.png',
             'folder-orange-2.png',
             'folder-orange-open.png',
             'folder-orange.png',
             'zip-2.png',
             'zip-3.png',
             'zip-4.png',
             'zip.png'])

        # Check that uninstalling works.
        for icon in files_after:
            book.uninstall_icon(icon)

        clean_icons = sorted(os.listdir(self.filename + "/__NOTEBOOK__/icons"))
        self.assertEqual(clean_icons, [])

        book.close()
