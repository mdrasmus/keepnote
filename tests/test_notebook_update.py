
# python imports
import shutil
import unittest

# keepnote imports
from keepnote.compat import notebook_v1
from keepnote.compat import notebook_v2
from keepnote.compat import notebook_v3
from keepnote.compat import notebook_v4
from keepnote import notebook
from keepnote.notebook import update

from . import clean_dir, TMP_DIR, DATA_DIR


def setup_old_notebook(old_version, new_version):

    # Setup paths.
    old_notebook_filename = DATA_DIR + "/notebook-v%s" % old_version
    new_notebook_filename = TMP_DIR + "/notebook-v%s-update" % new_version

    # make copy of old notebook
    clean_dir(new_notebook_filename)
    shutil.copytree(old_notebook_filename, new_notebook_filename)

    return new_notebook_filename


class Update (unittest.TestCase):

    def test_v1_to_latest(self):
        """test notebook update from version 1 to present."""

        # Setup paths.
        old_version = 1
        new_version = notebook.NOTEBOOK_FORMAT_VERSION
        notebook_filename = setup_old_notebook(old_version, new_version)

        # Load old notebook.
        book = notebook_v1.NoteBook()
        book.load(notebook_filename)
        old_attrs = dict(book._attr)

        # Update notebook (in place).
        update.update_notebook(notebook_filename, new_version, verify=True)

        # Load new notebook.
        book = notebook.NoteBook()
        book.load(notebook_filename)

        # Test for common error.
        new_attrs = dict(book.iter_attr())
        self.assertEqual(new_attrs['title'], old_attrs['title'])

        book.close()

    def test_v1_v2(self):

        # Setup paths.
        old_version = 1
        new_version = 2
        notebook_filename = setup_old_notebook(old_version, new_version)

        # Load old notebook.
        book = notebook_v1.NoteBook()
        book.load(notebook_filename)
        old_attrs = dict(book._attr)

        # Update notebook (in place).
        update.update_notebook(notebook_filename, new_version, verify=True)

        # Load new notebook.
        book = notebook_v2.NoteBook()
        book.load(notebook_filename)

        # Test for common error.
        self.assertEqual(book.get_title(), old_attrs['title'])

    def test_v2_v3(self):

        # Setup paths.
        old_version = 2
        new_version = 3
        notebook_filename = setup_old_notebook(old_version, new_version)

        # Load old notebook.
        book = notebook_v2.NoteBook()
        book.load(notebook_filename)
        old_attrs = dict(book._attr)

        # Update notebook (in place).
        update.update_notebook(notebook_filename, new_version, verify=True)

        # Load new notebook.
        book = notebook_v3.NoteBook()
        book.load(notebook_filename)

        # Test for common error.
        self.assertEqual(book.get_title(), old_attrs['title'])

    def test_v3_to_v4(self):

        # Setup paths.
        old_version = 3
        new_version = 4
        notebook_filename = setup_old_notebook(old_version, new_version)

        # Load old notebook.
        book = notebook_v3.NoteBook()
        book.load(notebook_filename)
        old_attrs = dict(book._attr)

        # Update notebook (in place).
        update.update_notebook(notebook_filename, new_version, verify=True)

        # Load new notebook.
        book = notebook_v4.NoteBook()
        book.load(notebook_filename)

        # Test for common error.
        self.assertEqual(book.get_title(), old_attrs['title'])

    def test_v4_to_latest(self):

        # Setup paths.
        old_version = 4
        new_version = notebook.NOTEBOOK_FORMAT_VERSION
        notebook_filename = setup_old_notebook(old_version, new_version)

        # Load old notebook.
        book = notebook_v4.NoteBook()
        book.load(notebook_filename)
        old_attrs = dict(book._attr)
        book.close()

        # Update notebook (in place).
        update.update_notebook(notebook_filename, new_version, verify=True)

        # Load new notebook.
        book = notebook.NoteBook()
        book.load(notebook_filename)

        # Test for common error.
        self.assertEqual(book.get_title(), old_attrs['title'])
        book.close()

    def test_v5_to_latest(self):

        # Setup paths.
        old_version = 5
        new_version = notebook.NOTEBOOK_FORMAT_VERSION
        notebook_filename = setup_old_notebook(old_version, new_version)

        # Update notebook (in place).
        update.update_notebook(notebook_filename, new_version, verify=True)

        # Load new notebook.
        book = notebook.NoteBook()
        book.load(notebook_filename)

        # Test for common error.
        old_title = 'Test Example Notebook'
        self.assertEqual(book.get_title(), old_title)
        book.close()

    def test_high(self):

        old_version = 'HIGH'
        new_version = notebook.NOTEBOOK_FORMAT_VERSION
        notebook_filename = setup_old_notebook(old_version, new_version)

        book = notebook.NoteBook()
        try:
            book.load(notebook_filename)
        except notebook.NoteBookVersionError:
            print "Correctly detects version error"
        else:
            print "Error not detected"
            self.assert_(False)
