#!/usr/bin/env python

# keepnote imports
from keepnote.gui.richtext.textbuffer_tools import TextBufferDom
from .test_richtext_html import display_item, BufferBase


class TestCaseRichTextBuffer (BufferBase):

    def test_dom(self):
        self.buffer.insert_at_cursor("hi there")

        # do bold insert
        bold = self.buffer.tag_table.lookup("bold")
        italic = self.buffer.tag_table.lookup("italic")
        self.buffer.toggle_tag_selected(bold)
        self.buffer.insert_at_cursor(" hello")
        self.buffer.toggle_tag_selected(italic)
        self.buffer.insert_at_cursor(" again")
        self.buffer.toggle_tag_selected(italic)
        self.buffer.insert_at_cursor(" this is me")
        self.assertEquals([display_item(x) for x in self.get_contents()],
                          ['hi there',
                           'BEGIN:bold',
                           ' hello',
                           'BEGIN:italic',
                           ' again',
                           'END:italic',
                           ' this is me',
                           'END:bold'])

        dom = TextBufferDom(self.get_contents())
        print
        dom.display()

        self.assertEquals([display_item(x) for x in dom.get_contents()],
                          ['hi there',
                           'BEGIN:bold',
                           ' hello',
                           'BEGIN:italic',
                           ' again',
                           'END:italic',
                           ' this is me',
                           'END:bold'])

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
        bold = self.buffer.tag_table.lookup("bold")
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
        bold = self.buffer.tag_table.lookup("bold")
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

        tag = self.buffer.tag_table.lookup("family Serif")
        self.buffer.apply_tag_selected(tag, self.buffer.get_start_iter(),
                                       self.buffer.get_end_iter())

        tag = self.buffer.tag_table.lookup("family Monospace")
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

        tag = self.buffer.tag_table.lookup("size 20")
        self.buffer.apply_tag_selected(tag, self.buffer.get_start_iter(),
                                       self.buffer.get_end_iter())

        tag = self.buffer.tag_table.lookup("size 30")
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
