#!/usr/bin/env python

# python import
import time
import sys
from StringIO import StringIO
from unittest import TestCase

# keepnote imports
from keepnote.gui.richtext.richtext_html import HtmlBuffer, nest_indent_tags, \
    find_paragraphs, P_TAG
from keepnote.gui.richtext import RichTextIO

from keepnote.gui.richtext.richtextbuffer import RichTextBuffer, ignore_tag, \
    RichTextIndentTag

from keepnote.gui.richtext.textbuffer_tools import \
    insert_buffer_contents, \
    normalize_tags, \
    iter_buffer_contents, \
    PushIter, \
    TextBufferDom


def display_item(item):
    """Return a string representing a buffer item"""

    if item[0] == "text":
        return item[2]
    elif item[0] == "begin":
        return "BEGIN:" + item[2].get_property('name')
    elif item[0] == "end":
        return "END:" + item[2].get_property('name')
    elif item[0] == "anchor":
        return item[0]
    else:
        return item[0] + ":" + item[2]


class BufferBase (TestCase):

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
                                         None, None, ignore_tag))


class Html (BufferBase):

    def setUp(self):
        BufferBase.setUp(self)
        self.io = HtmlBuffer()

    def read(self, buffer, infile):
        contents = list(self.io.read(infile, partial=True))
        self.insert(self.buffer, contents)

    def write(self, buffer, outfile):
        contents = iter_buffer_contents(self.buffer, None, None, ignore_tag)
        self.io.set_output(outfile)
        self.io.write(contents, self.buffer.tag_table, partial=True)

    def read_write(self, str_in, str_out=None):
        """Given the input string 'str_in' will the buffer write 'str_out'"""
        if str_out is None:
            str_out = str_in

        infile = StringIO(str_in)
        outfile = StringIO()

        # read/write
        self.read(self.buffer, infile)
        self.write(self.buffer, outfile)

        self.assertEquals(outfile.getvalue(), str_out)

    #===================================================

    def test_nested_tags(self):
        """Simple read/write, text should not change"""
        self.read_write("<nobr>x<u>a<i>b<b>c</b>d</i>e</u>y</nobr>")

    def test_unnormalized_input(self):
        """Tags should be normalized when writing,
           output should not be equal."""
        self.read_write("<b><i>hello</b></i>",
                        "<b><i>hello</i></b>")

    def test_normalized_tags(self):
        self.read_write("<i><b>hello</b>again</i>")

    def test_newlines(self):
        self.read_write("line1<br/>\n<br/>\nline2")

    def test_newlines2(self):
        self.read_write("line1<br/><br/>line2",
                        "line1<br/>\n<br/>\nline2")

    def test_entity(self):
        self.read_write("&#09;&amp;&gt;&lt; &nbsp; &nbsp; &nbsp;")

    def test_spacing(self):
        """Escaping multiple spaces"""
        self.read_write("&nbsp; &nbsp; &nbsp;")

    def test_spacing2(self):
        """First space will be literal, thus output should not be equal"""
        self.read_write("line1\nline2",
                        "line1 line2")

    def test_leading_space(self):
        """Do leading spaces remain preserved"""
        self.read_write("&nbsp;x")

        self.buffer.clear()
        self.read_write("&nbsp; x")

        self.buffer.clear()
        self.read(self.buffer, StringIO("<br>\n&nbsp;x"))
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['\n x'])

        self.buffer.clear()
        self.read_write("<br/>\n&nbsp;x")

    def test_read_hr(self):
        self.read(self.buffer, StringIO("line1<hr/>line2"))
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['line1\n',
                           'anchor',
                           '\nline2'])

        self.buffer.clear()
        self.read(self.buffer, StringIO("line1<hr/><br/>\nline2"))
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['line1\n',
                           'anchor',
                           '\n\nline2'])

        # what if <hr/> has newlines around it in HTML?
        self.buffer.clear()
        self.read(self.buffer, StringIO("line1\n<hr/>\n<br/>\nline2"))
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['line1 \n',
                           'anchor',
                           '\n \nline2'])

    def test_font_family(self):
        self.read_write('<span style="font-family: Serif">hello</span>')

    def test_font_size(self):
        self.read_write('<span style="font-size: 12pt">hello</span>')

    def test_font_justification(self):
        self.read(self.buffer, StringIO(
            '<div style="text-align: center">hello<br/>\nagain</div>'))

        #contents = normalize_tags(find_paragraphs(
        #    nest_indent_tags(self.get_contents(), self.buffer.tag_table)),
        #    is_stable_tag=lambda tag:
        #    isinstance(tag, RichTextIndentTag) or tag == P_TAG)

        #contents = find_paragraphs(
        #    nest_indent_tags(self.get_contents(), self.buffer.tag_table))
        #print ">>>", [display_item(x) for x in contents]

        self.buffer.clear()
        self.read_write(
            '<div style="text-align: center">hello<br/>\nagain</div>')

    def test_font_many(self):
        self.read_write(
            '<div style="text-align: center; font-size: 22pt; '
            'font-family: Serif">hello<br/>\nagain</div>',
            '<div style="text-align: center">'
            '<span style="font-family: Serif">'
            '<span style="font-size: 22pt">'
            'hello<br/>\nagain</span></span></div>')

    def test_hr(self):
        self.read_write('line1<hr/><br/>\nline2')
        self.buffer.clear()
        self.read_write('line1<hr/>line2')

    def test_font_other(self):
        contents = self.io.read(StringIO('<strong>hello</strong>'),
                                partial=True)
        self.assertEqual(map(display_item, contents),
                         ['beginstr:bold', 'hello', 'endstr:bold'])

        contents = self.io.read(StringIO('<em>hello</em>'),
                                partial=True)
        self.assertEqual(map(display_item, contents),
                         ['beginstr:italic', 'hello', 'endstr:italic'])

    def test_ol1(self):
        self.read_write(
            '<ul><li style="list-style-type: none">line1</li>\n'
            '<li style="list-style-type: none">line2</li>\n</ul>\n')

    def test_ol2(self):
        self.read_write(
            'line0<ul><li style="list-style-type: none">line1</li>\n'
            '<li style="list-style-type: none">line2</li>\n'
            '<li style="list-style-type: none"><ul>'
            '<li style="list-style-type: none">line3</li>\n'
            '<li style="list-style-type: none">line4</li>\n</ul>\n</li>\n'
            '<li style="list-style-type: none">line5</li>\n</ul>\nline6')

    def test_ol3(self):
        self.read_write(
            'line1<ul><li style="list-style-type: none">line1.5</li>\n'
            '<li style="list-style-type: none"><ul>'
            '<li style="list-style-type: none">line2</li>\n'
            '<li style="list-style-type: none">line3</li>\n</ul>'
            '\n</li>\n</ul>\nline4')

    def test_ol4(self):
        self.read_write(
            '<b><i>line0</i><ul><li style="list-style-type: none">'
            '<i>line1</i></li>\n'
            '<li style="list-style-type: none"><i>line2</i></li>\n'
            '<li style="list-style-type: none"><ul>'
            '<li style="list-style-type: none">line3</li>\n'
            '<li style="list-style-type: none">line4</li>\n'
            '</ul>\n</li>\n<li style="list-style-type: none">line5</li>\n'
            '</ul>\nline6</b>')

    def test_ol5(self):
        infile = StringIO(
            'line0<ul><li style="list-style-type: none">line1<br/>\n'
            'line2<ul><li style="list-style-type: none">line3<br/>\n'
            'line4<br/>\n</li>\n</ul>\n</li>\n'
            '<li style="list-style-type: none">line5</li>\n</ul>\nline6')
        self.read(self.buffer, infile)

        contents = list(iter_buffer_contents(self.buffer,
                                             None, None, ignore_tag))

        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents],
                          ['line0\n',
                           'BEGIN:indent 1 none',
                           'line1\nline2\n',
                           'END:indent 1 none',
                           'BEGIN:indent 2 none',
                           'line3\nline4\n\n',
                           'END:indent 2 none',
                           'BEGIN:indent 1 none',
                           'line5\n',
                           'END:indent 1 none',
                           'line6'])

    def test_ol6(self):
        infile = StringIO(
            'line0<ul><li style="list-style-type: none">line1<br/>\n'
            'line2<ul><li style="list-style-type: none">line3<br/>\n'
            'line4<br/>\n</li>\n</ul>\n'
            '</li>\n</ul>\nline5')
        self.read(self.buffer, infile)

        contents = list(iter_buffer_contents(self.buffer,
                                             None, None, ignore_tag))

        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents],
                          ['line0\n',
                           'BEGIN:indent 1 none',
                           'line1\nline2\n',
                           'END:indent 1 none',
                           'BEGIN:indent 2 none',
                           'line3\nline4\n\n',
                           'END:indent 2 none',
                           'line5'])

    def test_ol7(self):
        self.read_write(
            'line0<ul><li style="list-style-type: none">'
            '<ul><li style="list-style-type: none">line1</li>\n'
            '<li style="list-style-type: none">line2</li>\n</ul>\n</li>\n'
            '<li style="list-style-type: none">line3</li>\n'
            '</ul>\nline4')

    def test_bullet(self):
        self.buffer.insert_at_cursor("end1\nend2\n")
        self.buffer.place_cursor(self.buffer.get_start_iter())
        #self.buffer.indent()
        self.buffer.toggle_bullet_list()
        self.buffer.insert_at_cursor("line1\n")

        contents = list(iter_buffer_contents(self.buffer,
                                             None, None, ignore_tag))

        dom = TextBufferDom(
            normalize_tags(find_paragraphs(
                nest_indent_tags(self.get_contents(), self.buffer.tag_table)),
                is_stable_tag=lambda tag:
                isinstance(tag, RichTextIndentTag) or
                tag == P_TAG))
        self.io.prepare_dom_write(dom)
        print
        dom.display()

        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents],
                          ['BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line1\n',
                           'BEGIN:bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'end1\n',
                           'END:indent 1 bullet',
                           'end2\n'])

        outfile = StringIO()
        self.write(self.buffer, outfile)

        self.assertEquals(outfile.getvalue(),
                          '<ul><li>line1</li>\n'
                          '<li>end1</li>\n</ul>\nend2<br/>\n')

    def test_bullet2(self):
        self.read_write(
            '<b><i>line0</i><ul><li><i>line1</i></li>\n'
            '<li><i>line2</i></li>\n'
            '<li style="list-style-type: none"><ul><li>line3</li>\n'
            '<li>line4</li>\n</ul>\n</li>\n'
            '<li>line5</li>\n'
            '</ul>\nline6</b>')

    def test_par(self):
        self.read(self.buffer, StringIO(
            """word1 <b>word2<br/>\nword3</b> word4<br/>\n"""))

        contents = list(normalize_tags(
            find_paragraphs(self.get_contents()),
            is_stable_tag=lambda tag: tag == P_TAG))

        self.assertEquals([display_item(x) for x in contents],
                          ['BEGIN:p',
                           'word1 ',
                           'BEGIN:bold',
                           'word2\n',
                           'END:bold',
                           'END:p',
                           'BEGIN:bold',
                           'END:bold',
                           'BEGIN:p',
                           'BEGIN:bold',
                           'word3',
                           'END:bold',
                           ' word4\n',
                           'END:p'])

    def test_bullet3(self):
        """
        Test to see if current_tags is set from text to the right when
        cursor is at start of line
        """
        self.buffer.insert_at_cursor("\nend")
        self.buffer.place_cursor(self.buffer.get_start_iter())

        self.buffer.insert_at_cursor("line1")
        self.buffer.toggle_bullet_list()
        self.buffer.insert_at_cursor("\nline2")
        self.buffer.unindent()

        # move to start of "line2"
        it = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        it.backward_line()
        it.forward_line()
        self.buffer.place_cursor(it)

        # insert text, it should not be indented
        self.buffer.insert_at_cursor("new ")

        contents = list(iter_buffer_contents(self.buffer,
                                             None, None, ignore_tag))

        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents],
                          ['BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line1\n',
                           'END:indent 1 bullet',
                           'new line2\nend'])

    def test_bullet4(self):
        """
        Test undo toggle bullet
        """

        self.buffer.insert_at_cursor("line1")

        contents1 = list(iter_buffer_contents(self.buffer,
                                              None, None, ignore_tag))

        self.buffer.toggle_bullet_list()
        self.buffer.undo()

        contents2 = list(iter_buffer_contents(self.buffer,
                                              None, None, ignore_tag))

        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents1],
                          [display_item(x) for x in contents2])

    def test_bullet5(self):
        """
        Test undo toggle bullet with font
        """

        self.buffer.toggle_tag_selected(self.buffer.tag_table.lookup("bold"))
        self.buffer.insert_at_cursor("line1")

        contents1 = list(iter_buffer_contents(self.buffer,
                                              None, None, ignore_tag))

        self.buffer.toggle_bullet_list()

        print [display_item(x) for x in iter_buffer_contents(
            self.buffer, None, None, ignore_tag)]

        self.buffer.undo()

        contents2 = list(iter_buffer_contents(self.buffer,
                                              None, None, ignore_tag))

        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents1],
                          [display_item(x) for x in contents2])

    def test_bullet_insert(self):
        """
        Test whether insert inside bullet string '* ' is rejected
        """

        self.buffer.toggle_bullet_list()
        self.buffer.insert_at_cursor("line1")

        contents1 = list(iter_buffer_contents(self.buffer,
                                              None, None, ignore_tag))

        it = self.buffer.get_start_iter()
        it.forward_chars(1)
        self.buffer.insert(it, "XXX")

        contents2 = list(iter_buffer_contents(self.buffer,
                                              None, None, ignore_tag))

        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents1],
                          [display_item(x) for x in contents2])

    def test_bullet_apply_tag(self):
        """
        Test whether par_related tags are properly handled
        """

        self.buffer.toggle_bullet_list()
        self.buffer.insert_at_cursor("line1")

        it = self.buffer.get_start_iter()
        #it.forward_chars(1)
        it2 = self.buffer.get_start_iter()
        it2.forward_chars(2)

        tag = self.buffer.tag_table.lookup("indent 2 none")
        print tag.is_par_related()
        self.buffer.apply_tag_selected(tag, it, it2)

        contents1 = list(iter_buffer_contents(self.buffer,
                                              None, None, ignore_tag))

        # check the internal indentation structure
        self.assertEquals([display_item(x) for x in contents1],
                          ['BEGIN:indent 2 none',
                           u'line1\n',
                           'END:indent 2 none'])

    def test_bullet_blank_lines(self):
        """
        Make sure blank lines b/w bullets do not disappear
        """

        self.read(self.buffer, StringIO(
            '<ul><li>line1</li>\n'
            '</ul>\n'
            '<ul><li>line2</li>\n'
            '</ul>\n'))

        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line1\n',
                           'END:indent 1 bullet',
                           '\n',
                           'BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line2\n',
                           'END:indent 1 bullet'])

        self.buffer.clear()

        self.read_write(
            '<ul><li>line1</li>\n'
            '</ul>\n'
            '<br/>\n'
            '<ul><li>line2</li>\n'
            '</ul>\n')

    def test_bullet_newlines_deep_indent(self):
        """
        Make sure blank lines b/w bullets do not disappear
        """
        self.read(self.buffer, StringIO(
            '<ol><li style="list-style-type: none">'
            '<ol><li style="list-style-type: disc">line1</li>\n</ol>\n</li>\n'
            '<li style="list-style-type: disc"></li>\n'
            '</ol>\n'))

        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:bullet',
                           'BEGIN:indent 2 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line1\n',
                           'END:indent 2 bullet',
                           'BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           '\n',
                           'END:indent 1 bullet'])

    def test_bullet_new_lines(self):
        """
        Make sure newlines can be added at front of bullet
        """

        self.read(self.buffer, StringIO(
            '<ol><li style="list-style-type: disc">line1</li>\n'
            '</ol>\n'
            '<ol><li style="list-style-type: disc">line2</li>\n'
            '</ol>\n'))

        self.buffer.place_cursor(self.buffer.get_start_iter())
        self.buffer.insert_at_cursor("\n")

        '''
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['\n',
                           'BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line1\n',
                           'END:indent 1 bullet',
                           '\n',
                           'BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line2\n',
                           'END:indent 1 bullet'])
        '''

        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           '\n',
                           'BEGIN:bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line1\n',
                           'END:indent 1 bullet',
                           '\n',
                           'BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line2\n',
                           'END:indent 1 bullet'])

    def test_bullet_undo(self):
        """Make sure bullets interact with undo correctly"""

        self.read(self.buffer, StringIO(
            '''<ul><li>line1</li>
<li style="list-style-type: none"><ul><li>line2</li>
</ul>
</li>
</ul>'''))

        self.write(self.buffer, sys.stdout)

        self.buffer.undo()
        self.buffer.redo()

        self.write(self.buffer, sys.stdout)

        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['BEGIN:bullet',
                           'BEGIN:indent 1 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line1\n',
                           'END:indent 1 bullet',
                           'BEGIN:bullet',
                           'BEGIN:indent 2 bullet',
                           u'\u2022 ',
                           'END:bullet',
                           'line2\n',
                           'END:indent 2 bullet'])

    '''def test_bullet_delete(self):
        """Remove bullet with delete"""

        self.read(self.buffer, StringIO(
            """<ul><li>hello</li></ul>\n"""))

        print [display_item(x) for x in self.get_contents()]
        self.buffer.place_cursor(self.buffer.get_start_iter())
    '''

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

    def test_body(self):

        contents = list(self.io.read(StringIO(
            "<html><head><title>title</title></head>"
            "<body>Hello world</body></html>"),
            partial=False))
        self.assertEqual(contents, [('text', None, 'Hello world')])

        contents = list(self.io.read(StringIO("Hello world"),
                                     partial=True))
        self.assertEqual(contents, [('text', None, 'Hello world')])

    def test_comments(self):
        contents = self.io.read(StringIO(
            """<style><!-- comment --></style> hello <!--nice--> bye"""),
            partial=True)

        self.assertEqual(map(display_item, contents),
                         [' hello  bye'])


class Speed (TestCase):

    def _test_speed(self):
        buf = RichTextBuffer()
        io = RichTextIO()

        t = time.time()
        io.load(None, buf,
                "test/data/notebook-v4/stress tests/"
                "A huge page of formatted text/page.html")
        print time.time() - t
