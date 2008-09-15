
import unittest

from test_richtext_html import TestCaseHtmlBuffer
from takenote import notebook


class TestCaseNotebookChanges (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test_notebook1_to_2(self):
        book = notebook.NoteBook("test/data/notebook1")

        
notebook_changes_suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseNotebookChanges)

