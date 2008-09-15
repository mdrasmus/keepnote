
# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
import takenote
from takenote.undo import UndoStack

from takenote.gui.textbuffer_tools import \
     iter_buffer_contents, \
     buffer_contents_iter_to_offset, \
     normalize_tags, \
     insert_buffer_contents, \
     buffer_contents_apply_tags

# import tags
from takenote.gui.richtext_tags import \
     RichTextTagTable, \
     RichTextTag, \
     RichTextModTag, \
     RichTextJustifyTag, \
     RichTextFamilyTag, \
     RichTextSizeTag, \
     RichTextFGColorTag, \
     RichTextBGColorTag, \
     RichTextIndentTag, \
     RichTextBulletTag

from takenote.gui.richtextbasebuffer import \
     RichTextBaseBuffer, \
     RichTextFont, \
     add_child_to_buffer, \
     move_to_start_of_line, \
     move_to_end_of_line, \
     get_paragraph, \
     paragraph_iter, \
     get_paragraphs_selected



# string for bullet points
BULLET_STR = u"\u2022 "




#=============================================================================

class IndentManager (object):
    """This object will manage the indentation of paragraphs in a
       TextBuffer with RichTextTags
    """

    def __init__(self, textbuffer):
        self._buf = textbuffer
        self._updating = False

        self._indent_update = False
        self._indent_update_start = self._buf.create_mark("indent_update_start",
                                                     self._buf.get_start_iter(),
                                                     True)
        self._indent_update_end = self._buf.create_mark("indent_update_end",
                                                    self._buf.get_end_iter(),
                                                    False)
        self._bullet_mark = self._buf.create_mark("bullet",
                                                  self._buf.get_start_iter(),
                                                  True)



    def change_indent(self, start, end, change):
        """Change indentation level"""
        
        # determine region
        if start is None or end is None:
            start, end = get_paragraphs_selected(self._buf)

        self._buf.begin_user_action()
        
        # loop through paragraphs
        for pos in paragraph_iter(self._buf, start, end):
            par_end = pos.copy()
            par_end.forward_line()
            indent, par_indent = self.get_indent(pos)

            if indent + change > 0:
                self._buf.apply_tag_selected(
                    self._buf.tag_table.lookup_indent(indent + change,
                                                 par_indent),
                    pos, par_end)
                
            elif indent > 0:
                # remove indent and possible bullets
                self._buf.remove_tag_selected(
                    self._buf.tag_table.lookup_indent(indent, par_indent),
                                pos, par_end)                
                self._remove_bullet(pos)

            else:
                # do nothing
                pass


        self._buf.end_user_action()
        


    def toggle_bullet_list(self):
        """Toggle the state of a bullet list"""
        
        self._buf.begin_user_action()

        # round selection to nearest paragraph
        start, end = get_paragraphs_selected(self._buf)

        # trying to insert paragraph at end of buffer
        if start.compare(end) == 0:
            # insert a newline
            self._buf.insert_at_cursor("\n")
            end = self._buf.get_end_iter()
            start = end.copy()
            start.backward_line()
            self._buf.place_cursor(start)
        
        # are all paragraphs bulleted?
        all_bullets = True
        for pos in paragraph_iter(self._buf, start, end):
            if self.get_indent(pos)[1] != "bullet":
                all_bullets = False
                break

        # toggle bullet presence
        if all_bullets:
            par_type = "none"
        else:
            par_type = "bullet"

        # set each paragraph's bullet status
        for pos in paragraph_iter(self._buf, start, end):
            par_end = pos.copy()
            par_end.forward_line()
            self._set_bullet_list_paragraph(pos, par_end, par_type)
            
        self._buf.end_user_action()


    def _set_bullet_list_paragraph(self, par_start, par_end, par_type):
        """Toggle the state of a bullet list for a paragraph"""
        
        # start indent if it is not present
        indent, _ = self.get_indent(par_start)
        if indent == 0:
            indent = 1

        # apply indent to whole paragraph
        indent_tag = self._buf.tag_table.lookup_indent(indent, par_type)
        self._buf.apply_tag_selected(indent_tag, par_start, par_end)
        
        self._queue_update_indentation(par_start, par_end)        


    def _insert_bullet(self, par_start):
        """Insert a bullet point at the begining of the paragraph"""

        if self.par_has_bullet(par_start):
            return par_start
        
        self._buf.begin_user_action()

        # insert text
        self._buf.move_mark(self._bullet_mark, par_start)
        self._buf.insert(par_start, BULLET_STR)

        # apply tag to just the bullet point
        par_start = self._buf.get_iter_at_mark(self._bullet_mark)
        bullet_end = par_start.copy()
        bullet_end.forward_chars(len(BULLET_STR))
        bullet_tag = self._buf.tag_table.bullet_tag
        self._buf.apply_tag_selected(bullet_tag, par_start, bullet_end)

        self._buf.end_user_action()

        return par_start

    def _remove_bullet(self, par_start):
        """Remove a bullet point from the paragraph"""

        self._buf.begin_user_action()
        
        bullet_end = par_start.copy()
        bullet_end.forward_chars(len(BULLET_STR))
        self._buf.move_mark(self._bullet_mark, par_start)

        if par_start.get_text(bullet_end) == BULLET_STR:
            bullet_tag = self._buf.tag_table.bullet_tag
            self._buf.remove_tag_selected(bullet_tag, par_start, bullet_end)
            self._buf.delete(par_start, bullet_end)

        self._buf.end_user_action()

        return self._buf.get_iter_at_mark(self._bullet_mark)
 

    def par_has_bullet(self, par_start):
        """Returns True if paragraph starts with bullet point"""
        bullet_end = par_start.copy()
        bullet_end.forward_chars(len(BULLET_STR))

        return par_start.get_text(bullet_end) == BULLET_STR


    def on_paragraph_merge(self, start, end):
        """Callback for when paragraphs have merged"""
        self._queue_update_indentation(start, end)


    def on_paragraph_split(self, start, end):
        """Callback for when paragraphs have split"""
        self._queue_update_indentation(start, end)


    def on_paragraph_change(self, start, end):
        """Callback for when the tags of a paragraph changes"""

        if not self._updating:
            start = move_to_start_of_line(start.copy())
            end = move_to_end_of_line(end.copy())
            self._queue_update_indentation(start, end)
    

    def _queue_update_indentation(self, start, end):
        """Queues an indentation update"""
        
        if not self._indent_update:
            # first update
            self._indent_update = True
            self._buf.move_mark(self._indent_update_start, start)
            self._buf.move_mark(self._indent_update_end, end)
        else:
            # expand update region
            a = self._buf.get_iter_at_mark(self._indent_update_start)
            b = self._buf.get_iter_at_mark(self._indent_update_end)

            if start.compare(a) == -1:
                self._buf.move_mark(self._indent_update_start, start)

            if end.compare(b) == 1:
                self._buf.move_mark(self._indent_update_end, end)


    def update_indentation(self):
        """Ensure the indentation tags between start and end are up to date"""

        # fixup indentation tags
        # The general rule is that the indentation at the start of
        # each paragraph should determines the indentation of the rest
        # of the paragraph

        if self._indent_update:
            self._updating = True
            self._indent_update = False 
            
            self._buf.begin_user_action()
            
            # get range of updating
            pos = self._buf.get_iter_at_mark(self._indent_update_start)
            end = self._buf.get_iter_at_mark(self._indent_update_end)
            pos = move_to_start_of_line(pos)
            end.forward_line()
            
            # iterate through the paragraphs that need updating
            for pos in paragraph_iter(self._buf, pos, end):                
                par_end = pos.copy()
                par_end.forward_line()
                indent_tag = self.get_indent_tag(pos)

                # remove bullets mid paragraph
                it = pos.copy()
                it.forward_char()
                while True:
                    match = it.forward_search(BULLET_STR, 0, par_end)
                    if not match:
                        it.backward_char()
                        pos, par_end = get_paragraph(it)
                        break
                    self._buf.move_mark(self._indent_update_start, match[0])
                    self._buf.delete(match[0], match[1])
                    it = self._buf.get_iter_at_mark(self._indent_update_start)
                    par_end = it.copy()
                    par_end.forward_line()

                # check indentation
                if indent_tag is None:
                    # remove all indent tags
                    # TODO: RichTextBaseBuffer function
                    self._buf.clear_tag_class(self._buf.tag_table.lookup_indent(1),
                                         pos, par_end)
                    # remove bullets
                    par_type = "none"

                else:
                    self._buf.apply_tag_selected(indent_tag, pos, par_end)

                    # check for bullets
                    par_type = indent_tag.get_par_indent()

                # check paragraph type
                if par_type == "bullet":
                    # ensure proper bullet is in place
                    pos = self._insert_bullet(pos)
                    end = self._buf.get_iter_at_mark(self._indent_update_end)
                    
                elif par_type == "none":
                    # remove bullets
                    pos = self._remove_bullet(pos)
                    end = self._buf.get_iter_at_mark(self._indent_update_end)
                    
                else:
                    raise Exception("unknown par_type '%s'" % par_type)
                    
            self._updating = False
            self._buf.end_user_action()


    #==========================================
    # query and navigate paragraphs/indentation

    def get_indent(self, it=None):
        """Returns the indentation level at iter 'it'"""
        
        tag = self.get_indent_tag(it)
        if tag:
            return tag.get_indent(), tag.get_par_indent()
        else:
            return 0, "none"


    def get_indent_tag(self, it=None):
        """Returns the indentation level at iter 'it'"""
        
        if not it:
            it = self._buf.get_iter_at_mark(self._buf.get_insert())

        it2 = it.copy()
        if not it2.ends_line():
            it2.forward_char()
        
        for tag in it2.get_tags():
            if isinstance(tag, RichTextIndentTag):
                return tag
        
        return None        

    
    def starts_par(self, it):
        """Returns True if iter 'it' starts paragraph (or is within bullet)"""

        if it.starts_line():
            return True
        else:
            # handle case where it is within bullet
            it2 = it.copy()
            it2 = move_to_start_of_line(it2)
            
            return self.par_has_bullet(it2) and \
                   it.get_offset() <= it2.get_offset() + len(BULLET_STR)

    
    def _get_cursor(self):
        return self._buf.get_iter_at_mark(self._buf.get_insert())
