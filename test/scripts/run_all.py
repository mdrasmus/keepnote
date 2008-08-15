#!/usr/bin/env python


import sys
import unittest

sys.path.append("../..")
# takenote imports
from takenote.gui.richtext_html import HtmlBuffer

import StringIO
from takenote.gui.richtextbuffer import RichTextBuffer, IGNORE_TAGS
from takenote.gui.textbuffer_tools import \
     insert_buffer_contents, \
     iter_buffer_contents


class TestCaseHtmlBuffer (unittest.TestCase):
    
    def setUp(self):
        self.io = HtmlBuffer()
        self.buffer = RichTextBuffer()

    #def tearDown(self):
    #    pass

    def insert(self, buffer, contents):
        insert_buffer_contents(
            buffer,
            buffer.get_iter_at_mark(
                buffer.get_insert()),
            contents,
            add_child=lambda buffer, it, anchor: buffer.add_child(it, anchor),
            lookup_tag=lambda tagstr: buffer.tag_table.lookup(tagstr))

    def read(self, buffer, infile):
        contents = list(self.io.read(infile, partial=True))        
        self.insert(self.buffer, contents)

    def write(self, buffer, outfile):
        contents = iter_buffer_contents(self.buffer,
                                        None,
                                        None,
                                        IGNORE_TAGS)
        self.io.set_output(outfile)
        self.io.write(contents, partial=True)


    #===================================================

    def test_nested_tags(self):
        """Simple read/write, text should not change"""
        infile = StringIO.StringIO("<nobr>x<u>a<i>b<b>c</b>d</i>e</u>y</nobr>")
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)

        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_normalized_tags1(self):
        """Tags should be normalized when writing,
           output should not be equal."""
        infile = StringIO.StringIO("<b><i>hello</b></i>")
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertNotEquals(outfile.getvalue(), infile.getvalue())


    def test_normalized_tags2(self):
        infile = StringIO.StringIO("<b><i>hello</i></b><i>again</i>")
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_newlines(self):
        infile = StringIO.StringIO("line1<br/>\n<br/>\nline2")
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_entity(self):
        infile = StringIO.StringIO("&#09;&amp;&gt;&lt; &nbsp; &nbsp; &nbsp;")
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_spacing(self):
        """First space will be literal, thus output should not be equal"""
        infile = StringIO.StringIO("&nbsp; &nbsp; &nbsp;")
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertNotEquals(outfile.getvalue(), infile.getvalue())


    def test_font_family(self):
        infile = StringIO.StringIO('<span style="font-family: Serif">hello</span>')
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_font_size(self):
        infile = StringIO.StringIO('<span style="font-size: 12pt">hello</span>')
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_font_justification(self):
        infile = StringIO.StringIO('<div style="text-align: center">hello<br/>\nagain</div>')
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_font_many(self):
        infile = StringIO.StringIO('<div style="text-align: center; font-size: 22pt; font-family: Serif">hello<br/>\nagain</div>')
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(),
                          '<div style="text-align: center">'
                          '<span style="font-size: 22pt">'
                          '<span style="font-family: Serif">'
                          'hello<br/>\nagain</span></span></div>')

    def test_hr(self):
        infile = StringIO.StringIO('line1<hr/><br/>\nline2')
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())

        infile = StringIO.StringIO('line1<hr/>line2')
        outfile = StringIO.StringIO()

        # read/write
        self.buffer.clear()
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_ul2(self):
        infile = StringIO.StringIO('<ul>line1<br/>\nline2</ul>')
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())

        
    def test_ul3(self):
        infile = StringIO.StringIO('line0<ul>line1<br/>\n'
                                   'line2<ul>line3<br/>\n'
                                   'line4<br/>\n</ul>line5</ul>line6')
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())


    def test_image1(self):
        """Simple read/write, text should not change"""
        infile = StringIO.StringIO('<img src="filename.png" width="100" height="20" />')
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)
        self.assertEquals(outfile.getvalue(), infile.getvalue())




#unittest.main()
suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCaseHtmlBuffer)
unittest.TextTestRunner(verbosity=2).run(suite)
