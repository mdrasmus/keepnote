import os, shutil, unittest

from richtext_html import TestCaseHtmlBuffer

# takenote imports
from takenote import notebook

from takenote.gui.richtext_html import HtmlBuffer, nest_indent_tags, \
     find_paragraphs, P_TAG

import StringIO
from takenote.gui.richtextbuffer import RichTextBuffer, IGNORE_TAGS, \
     RichTextIndentTag

from takenote.gui.textbuffer_tools import \
     insert_buffer_contents, \
     normalize_tags, \
     iter_buffer_contents, \
     PushIter, \
     TextBufferDom



class TestCaseNotebookChanges (unittest.TestCase):
    
    def setUp(self):      
        pass


    def setUp_buffer(self):
        self.buffer = RichTextBuffer()
        self.io = HtmlBuffer()

    def insert(self, buffer, contents):
        insert_buffer_contents(
            buffer,
            buffer.get_iter_at_mark(
                buffer.get_insert()),
            contents,
            add_child=lambda buffer, it, anchor: buffer.add_child(it, anchor),
            lookup_tag=lambda tagstr: buffer.tag_table.lookup(tagstr))


    def get_contents(self):
        return list(iter_buffer_contents(self.buffer,
                                         None, None, IGNORE_TAGS))

    def read(self, buffer, infile):
        contents = list(self.io.read(infile))
        self.insert(self.buffer, contents)

    def write(self, buffer, outfile):
        contents = iter_buffer_contents(self.buffer,
                                        None,
                                        None,
                                        IGNORE_TAGS)
        self.io.set_output(outfile)
        self.io.write(contents, self.buffer.tag_table)



    def test_notebook1_to_2(self):

        self.setUp_buffer()
        
        if os.path.exists("test/data/notebook-v1-2"):
            shutil.rmtree("test/data/notebook-v1-2")
        shutil.copytree("test/data/notebook-v1",
                        "test/data/notebook-v1-2")

        
        
        book = notebook.NoteBook()
        book.load("test/data/notebook-v1-2")
        book.save(force=True)

        def walk(node):
            if node.is_page():
                print "rewrite", node.get_data_file()
                
                filename = node.get_data_file()
                self.buffer.clear()
                infile = open(filename)
                self.read(self.buffer, infile)
                infile.close()

                outfile = open(filename, "w")
                self.write(self.buffer, outfile)
                outfile.close()
            
            for child in node.get_children():
                walk(child)
        walk(book)

        # should be no differences
        print "differences"
        os.system("diff -r test/data/notebook-v1{,-2} > test/data/notebook-v1-2.tmp")
        self.assertEquals(os.system("diff test/data/notebook-v1-2.{tmp,diff}"),
                          0)

        
notebook_changes_suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseNotebookChanges)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(notebook_changes_suite)

