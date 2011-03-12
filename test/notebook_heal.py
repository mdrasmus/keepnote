


from testing import *

# python imports
import unittest, os, sys, shutil

# keepnote imports
from keepnote import notebook, safefile
import keepnote.notebook.connection as connlib



class Heal (unittest.TestCase):

    def test_no_index(self):
        
        # initialize two notebooks
        make_clean_dir("test/data/notebook_heal")

        book = notebook.NoteBook("test/data/notebook_heal/n1")
        book.create()
        book.close()

        # remove index
        os.remove("test/data/notebook_heal/n1/__NOTEBOOK__/index.sqlite")

        # try to load again
        book = notebook.NoteBook()
        book.load("test/data/notebook_heal/n1")
        assert "index.sqlite" in os.listdir(
            "test/data/notebook_heal/n1/__NOTEBOOK__")
        book.close()


    def test_bad_node(self):
        
        # initialize two notebooks
        make_clean_dir("test/data/notebook_heal")

        book = notebook.NoteBook("test/data/notebook_heal/n1")
        book.create()
        book.close()

        # corrupt node
        out = open("test/data/notebook_heal/n1/node.xml", "w")
        out.write("jsakhdfjhdsfh")
        out.close()

        # try to load again
        book = notebook.NoteBook()
        book.load("test/data/notebook_heal/n1")
        book.close()

        # check that node is valid xml
        assert open("test/data/notebook_heal/n1/node.xml").read().startswith("<?xml")

        # check that old node file was stored in lost and found
        assert "node.xml" in os.listdir(
            "test/data/notebook_heal/n1/__NOTEBOOK__/lost_found")
        


        # corrupt node
        out = open("test/data/notebook_heal/n1/node.xml", "w")
        out.write("jsakhdfjhdsfh")
        out.close()

        # try to load again
        book = notebook.NoteBook()
        book.load("test/data/notebook_heal/n1")
        book.close()

        # check that node is valid xml
        assert open("test/data/notebook_heal/n1/node.xml").read().startswith("<?xml")

        # check that old node file was stored in lost and found
        assert "node.xml-2" in os.listdir(
            "test/data/notebook_heal/n1/__NOTEBOOK__/lost_found")



    def test_bad_index(self):
        
        # initialize two notebooks
        make_clean_dir("test/data/notebook_heal")

        book = notebook.NoteBook("test/data/notebook_heal/n1")
        book.create()
        book.close()

        # corrupt index
        out = open("test/data/notebook_heal/n1/__NOTEBOOK__/index.sqlite", "w")
        out.write("jsakhdfjhdsfh")
        out.close()

        # try to load again
        book = notebook.NoteBook()
        book.load("test/data/notebook_heal/n1")

        print "corrupt", book._conn._index.is_corrupt()
        print "index_needed", book.index_needed()

        book.close()
        



        
        
if __name__ == "__main__":
    unittest.main()

