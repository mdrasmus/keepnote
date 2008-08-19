#!/usr/bin/env python


import sys
import unittest

# takenote imports
from takenote.gui.richtext_html import HtmlBuffer

import StringIO
from takenote.gui.richtextbuffer import RichTextBuffer, IGNORE_TAGS
from takenote.gui.textbuffer_tools import \
     insert_buffer_contents, \
     iter_buffer_contents, \
     PushIter


def display_item(item):
    """Return a string representing a buffer item"""
    
    if item[0] == "text":
        return item[2]
    elif item[0] == "begin":
        return "BEGIN:" + item[2].get_property('name')
    elif item[0] == "end":
        return "END:" + item[2].get_property('name')
    else:
        return item[0]


class TestCaseRichTextBufferBase (unittest.TestCase):

    def setUp(self):
        self.buffer = RichTextBuffer()

    def tearDown(self):
        self.buffer.clear()

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


class TestCaseRichTextBuffer (TestCaseRichTextBufferBase):      

    def test_undo_insert(self):
        """Text insert with current font can be undone"""
        self.buffer.insert_at_cursor("hi there")
        self.buffer.insert_at_cursor(" again")

        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['hi there again'])

        # undo insert
        self.buffer.undo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['hi there'])

        # undo insert
        self.buffer.undo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          [])

        # redo insert
        self.buffer.redo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['hi there'])

        
        # do bold insert
        bold = self.buffer.tag_table.bold_tag
        self.buffer.toggle_tag_selected(bold)
        self.buffer.insert_at_cursor(" hello")
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['hi there',
                           'BEGIN:bold',
                           ' hello',
                           'END:bold'])

        # undo bold insert
        self.buffer.undo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['hi there'])

        # undo everything
        self.buffer.undo()
        self.buffer.undo()        
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          [])

        # redo first insert
        self.buffer.redo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['hi there'])

        # redo bold insert
        self.buffer.redo()
        self.buffer.redo()        
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['hi there',
                           'BEGIN:bold',
                           ' hello',
                           'END:bold'])


    def test_undo_insert2(self):
        """Text insert with current font can be undone"""

        # do bold insert
        bold = self.buffer.tag_table.bold_tag
        self.buffer.toggle_tag_selected(bold)
        self.buffer.insert_at_cursor("hi there")
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:bold',
                           'hi there',
                           'END:bold'])

        # do unbold insert
        self.buffer.toggle_tag_selected(bold)
        self.buffer.insert_at_cursor(" hello")        
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:bold',
                           'hi there',
                           'END:bold',
                           ' hello'])

        # undo bold insert
        self.buffer.undo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:bold',
                           'hi there',
                           'END:bold'])
        

        # redo unbold insert
        # TEST: bug was that ' hello' would also be bold
        self.buffer.redo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:bold',
                           'hi there',
                           'END:bold',
                           ' hello'])

        

    def test_undo_family(self):
        """Font family change can be undone"""
        
        self.buffer.insert_at_cursor("hello")
        
        tag = self.buffer.tag_table.lookup_family("Serif")
        self.buffer.apply_tag_selected(tag, self.buffer.get_start_iter(),
                                       self.buffer.get_end_iter())

        tag = self.buffer.tag_table.lookup_family("Monospace")
        self.buffer.apply_tag_selected(tag, self.buffer.get_start_iter(),
                                       self.buffer.get_end_iter())

        self.buffer.undo()
        
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:family Serif',
                           'hello',
                           'END:family Serif'])

        self.buffer.redo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:family Monospace',
                           'hello',
                           'END:family Monospace'])



    def test_undo_size(self):
        """Font size change can be undone"""
        self.buffer.insert_at_cursor("hello")
        
        tag = self.buffer.tag_table.lookup_size(20)
        self.buffer.apply_tag_selected(tag, self.buffer.get_start_iter(),
                                       self.buffer.get_end_iter())

        tag = self.buffer.tag_table.lookup_size(30)
        self.buffer.apply_tag_selected(tag, self.buffer.get_start_iter(),
                                       self.buffer.get_end_iter())

        self.buffer.undo()        
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:size 20',
                           'hello',
                           'END:size 20'])

        self.buffer.redo()
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:size 30',
                           'hello',
                           'END:size 30'])

richtextbuffer_suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseRichTextBuffer)

    

class TestCaseHtmlBuffer (TestCaseRichTextBufferBase):
    
    def setUp(self):
        TestCaseRichTextBufferBase.setUp(self)
        self.io = HtmlBuffer()


    def read(self, buffer, infile):
        contents = list(self.io.read(infile, partial=True))        
        self.insert(self.buffer, contents)

    def write(self, buffer, outfile):
        contents = iter_buffer_contents(self.buffer,
                                        None,
                                        None,
                                        IGNORE_TAGS)
        self.io.set_output(outfile)
        self.io.write(contents, self.buffer.tag_table, partial=True)


    def read_write(self, str_in, str_out=None):
        """Given the input string 'str_in' will the buffer write 'str_out'"""
        if str_out is None:
            str_out = str_in

        infile = StringIO.StringIO(str_in)
        outfile = StringIO.StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)

        self.assertEquals(outfile.getvalue(), str_out)

    #===================================================


    #def test_iter_buffer(self):
    #    infile = StringIO.StringIO('<b>hello world</b>')
    #    self.read(self.buffer, infile)
    #
    #    print list(iter_buffer_contents(self.buffer, None, None, IGNORE_TAGS))
        

    def test_nested_tags(self):
        """Simple read/write, text should not change"""
        self.read_write("<nobr>x<u>a<i>b<b>c</b>d</i>e</u>y</nobr>")


    def test_unnormalized_input(self):
        """Tags should be normalized when writing,
           output should not be equal."""
        self.read_write("<b><i>hello</b></i>",
                        "<b>hello</b>")

    def test_normalized_tags(self):
        self.read_write("<b><i>hello</i></b><i>again</i>")

    def test_newlines(self):
        self.read_write("line1<br/>\n<br/>\nline2")

    def test_entity(self):
        self.read_write("&#09;&amp;&gt;&lt; &nbsp; &nbsp; &nbsp;")

    def test_spacing(self):
        """First space will be literal, thus output should not be equal"""
        self.read_write("&nbsp; &nbsp; &nbsp;",
                        " &nbsp; &nbsp; ")

    def test_font_family(self):
        self.read_write('<span style="font-family: Serif">hello</span>')

    def test_font_size(self):
        self.read_write('<span style="font-size: 12pt">hello</span>')

    def test_font_justification(self):
        self.read_write('<div style="text-align: center">hello<br/>\nagain</div>')

    def test_font_many(self):
        self.read_write('<div style="text-align: center; font-size: 22pt; font-family: Serif">hello<br/>\nagain</div>',
                        '<div style="text-align: center">'
                        '<span style="font-size: 22pt">'
                        '<span style="font-family: Serif">'
                        'hello<br/>\nagain</span></span></div>')

    def test_hr(self):
        self.read_write('line1<hr/><br/>\nline2')
        self.buffer.clear()        
        self.read_write('line1<hr/>line2')

    def test_ul1(self):
        self.read_write('<ul>line1<br/>\nline2</ul>')
        
    def test_ul2(self):
        self.read_write('line0<ul>line1<br/>\n'
                        'line2<ul>line3<br/>\n'
                        'line4<br/>\n</ul>line5</ul>line6')

    def test_ul3(self):
        self.read_write('line1<ul>line1.5<ul>line2<br/>\n'
                        'line3<br/>\n</ul></ul>line4')

    def test_ul4(self):
        self.read_write('<b><i>line0</i><ul><i>line1<br/>\n'
                        'line2</i><ul>line3<br/>\n'
                        'line4<br/>\n</ul>line5</ul>line6</b>')

    def test_ul5(self):
        infile = StringIO.StringIO('line0<ul>line1<br/>\n'
                                   'line2<ul>line3<br/>\n'
                                   'line4<br/>\n</ul>line5</ul>line6')
        self.read(self.buffer, infile)

        contents = list(iter_buffer_contents(self.buffer,
                                             None, None, IGNORE_TAGS))
        
        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents],
                          ['line0',
                           'BEGIN:indent 1',
                           'line1\nline2',
                           'END:indent 1',
                           'BEGIN:indent 2',
                           'line3\nline4\n',
                           'END:indent 2',
                           'BEGIN:indent 1',
                           'line5',
                           'END:indent 1',
                           'line6'])

    def test_ul6(self):
        infile = StringIO.StringIO('line0<ul>line1<br/>\n'
                                   'line2<ul>line3<br/>\n'
                                   'line4<br/>\n</ul></ul>line5')
        self.read(self.buffer, infile)

        contents = list(iter_buffer_contents(self.buffer,
                                             None, None, IGNORE_TAGS))
        
        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents],
                          ['line0',
                           'BEGIN:indent 1',
                           'line1\nline2',
                           'END:indent 1',
                           'BEGIN:indent 2',
                           'line3\nline4\n',
                           'END:indent 2',
                           'line5'])

    def test_ul7(self):
        self.read_write('line0<ul><ul>line1<br/>\n'
                        'line2<br/>\n</ul>line3</ul>line4')



        
    def test_image1(self):
        """Simple read/write, text should not change"""
        self.read_write('<img src="filename.png" width="100" height="20" />')


    def test_PushIter(self):
        """Test the PushIter class"""

        lst = []
        it = PushIter(xrange(10))

        lst.append(it.next())
        lst.append(it.next())
        lst.append(it.next())

        it.push('c')
        it.push('b')
        it.push('a')

        for i in reversed(lst):
            it.push(i)

        lst2 = list(it)

        self.assertEquals(lst2, [0, 1, 2, 'a', 'b', 'c', 3, 4, 5, 6, 7, 8, 9])
        
htmlbuffer_suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    TestCaseHtmlBuffer)
