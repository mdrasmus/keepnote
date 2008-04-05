
import sys, os, tempfile, re
from HTMLParser import HTMLParser


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
import gtk.gdk

from takenotelib.undo import UndoStack


# TODO: copy and paste child elements
# TODO: propper undo tags

#=============================================================================
# functions for iterating and inserting into textbuffers

def iter_buffer(textbuffer, start=None, end=None):
    """Iterate over the items of a textbuffer"""
    
    if start == None:
        it = textbuffer.get_start_iter()
    else:
        it = start.copy()
    last = it.copy()

    if end == None:
        end = textbuffer.get_end_iter()


    # yield opening tags
    for tag in it.get_tags():
        yield ("begin", it, last, tag)
    
    while True:
        it2 = it.copy()    
        it.forward_to_tag_toggle(None)

        # yield child anchors between tags        
        while True:
            if it.get_offset() < end.get_offset():
                stop = it
            else:
                stop = end
            ret = it2.forward_search(u'\ufffc', (), stop)
            
            if ret == None:
                yield ("text", it2, stop, it2.get_text(stop))
                break
            
            a, b = ret
            anchor = a.get_child_anchor()
            
            # yield text in between tags
            yield ("text", it2, a, it2.get_text(a))
            if anchor != None:
                yield ("anchor", a, b, (anchor, anchor.get_widgets()))
            else:
                yield ("pixbuf", a, b, a.get_pixbuf())
            it2 = b
        
        if it.get_offset() > end.get_offset():
            break
        
        # yield closing tags
        for tag in it.get_toggled_tags(False):
            yield ("end", it, last, tag)

        # yield opening tags
        for tag in it.get_toggled_tags(True):
            yield ("begin", it, last, tag)
        
        last = it.copy()
        
        if it.equal(end):
            break
    
    toggled = set(end.get_toggled_tags(False))
    for tag in end.get_tags():
        if tag not in toggled:
            yield ("end", end, last, tag)


def normalize_tags(items):
    open_stack = []

    for item in items:
        kind, it, last, param = item
        if kind == "begin":
            open_stack.append(param)
            yield item

        elif kind == "end":

            # close any open out of order tags
            reopen_stack = []
            while param != open_stack[-1]:
                reopen_stack.append(open_stack.pop())
                tag2 = reopen_stack[-1]
                yield ("end", it, last, tag2)

            # close current tag
            open_stack.pop()
            yield item

            # reopen tags
            for tag2 in reversed(reopen_stack):
                open_stack.append(tag2)
                yield ("begin", it, last, tag2)

        else:
            yield item


def insert_buffer_contents(textview, pos, contents):
    textbuffer = textview.get_buffer()
    
    textbuffer.place_cursor(pos)
    tags = {}
    
    # make sure all tags are removed on first text/anchor insert
    first_insert = True
    
    for item in contents:
        kind, it, last, param = item
        if kind == "text":
            textbuffer.insert_at_cursor(param)
            if first_insert:
                it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
                it2 = it.copy()
                it2.backward_chars(len(param))
                textbuffer.remove_all_tags(it2, it)
                first_insert = False
            
        elif kind == "anchor":
            it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
            anchor = textbuffer.create_child_anchor(it)
            child = param[1][0].get_owner().refresh()
            textview.add_child_at_anchor(child, anchor)
            
            if first_insert:
                it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
                it2 = it.copy()
                it2.backward_chars(len(param))
                textbuffer.remove_all_tags(it2, it)
                first_insert = False
            
        elif kind == "begin":
            tags[param] = textbuffer.get_iter_at_mark(textbuffer.get_insert()).get_offset()
            
        elif kind == "end":
            start = textbuffer.get_iter_at_offset(tags[param])
            end = textbuffer.get_iter_at_mark(textbuffer.get_insert())
            textbuffer.apply_tag(param, start, end)


#=============================================================================
# HTML parser for RichText

class HtmlBuffer (HTMLParser):
    """Read and write HTML for a gtk.TextBuffer"""
    
    def __init__(self, out=None):
        HTMLParser.__init__(self)
    
        self.out = out
        self.tag2html = {}
        self.html2tag = {}
        self.size_tags = set()
        self.family_tags = set()
        self.tag_stack = []
        self.richtext = None
        self.buffer = None
        
        self.entity_char_map = [("&", "amp"),
                                (">", "gt"),
                                ("<", "lt")]
        self.entity2char = {}
        for ch, name in self.entity_char_map:
            self.entity2char[name] = ch
    
    def set_output(self, out):
        self.out = out
    
    
    def add_tag(self, tag, html_name):
        self.tag2html[tag] = html_name
        self.html2tag[html_name] = tag
    
    
    def add_size_tag(self, tag):
        self.size_tags.add(tag)
    
    
    def add_family_tag(self, tag):
        self.family_tags.add(tag)
    
    
    def read(self, richtext, infile):
        self.richtext = richtext
        self.buffer = richtext.textbuffer
        
        for line in infile:
            self.feed(line)
        
        self.buffer.place_cursor(self.buffer.get_start_iter())
    
    
    def handle_starttag(self, tag, attrs):
        if tag in ("html", "body"):
            return
    
        mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), True)
        self.tag_stack.append((tag, attrs, mark))


    def handle_endtag(self, tag):
        if tag in ("html", "body"):
            return
    
        assert self.tag_stack[-1][0] == tag
        htmltag, attrs, mark = self.tag_stack.pop()
        
        if htmltag in self.html2tag:
            # get simple fonts b/i/u
            tag = self.html2tag[htmltag]
            
        elif htmltag == "br":
            # insert newline
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            return
            
        elif htmltag == "span":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("font-size"):
                        size = int(value.split(":")[1].replace("pt", ""))
                        tag = self.richtext.lookup_size_tag(size)
                        
                    elif value.startswith("font-family"):
                        family = value.split(":")[1].strip()
                        tag = self.richtext.lookup_family_tag(family)
                        
                    else:
                        raise Exception("unknown style '%s'" % value)
                else:
                    raise Exception("unknown attr key '%s'" % key)
        
        else:
            raise Exception("WARNING: unhandled tag '%s'" % htmltag)
            
        start = self.buffer.get_iter_at_mark(mark)
        self.buffer.apply_tag(tag, start, self.buffer.get_end_iter())
        self.buffer.delete_mark(mark)

    def handle_data(self, data):
        data = re.sub("[\n ]+", " ", data)
        self.buffer.insert(self.buffer.get_end_iter(), data)
    
    def handle_entityref(self, name):
        self.buffer.insert(self.buffer.get_end_iter(),
                           self.entity2char.get(name, ""))
            
    
    def write(self, richtext):
        textbuffer = richtext.textbuffer
        
        self.out.write("<html><body>")
        
        for kind, it, last, param in normalize_tags(iter_buffer(textbuffer)):
            if kind == "text":
                text = param
                text = text.replace("&", "&amp;")
                text = text.replace(">", "&gt;")
                text = text.replace("<", "&lt;")
                text = text.replace("\n", "<br/>\n")
                self.out.write(text)
            
            elif kind == "begin":
                tag = param
                self.write_tag_begin(tag)
                
            elif kind == "end":
                tag = param
                self.write_tag_end(tag)
            
            elif kind == "anchor":
                for widget in param[1]:
                    self.out.write("<img>")
            
            elif kind == "pixbuf":
                self.out.write("<pixbuf>")
        
        self.out.write("</body></html>")
        
    
    def write_tag_begin(self, tag):
        if tag in self.tag2html:
            self.out.write("<%s>" % self.tag2html[tag])
        else:
            if tag in self.size_tags:
                self.out.write("<span style='font-size: %dpt'>" % 
                          tag.get_property("size-points"))
            elif tag in self.family_tags:
                self.out.write("<span style='font-family: %s'>" % 
                          tag.get_property("family"))
            else:
                raise Exception("unknown tag")
                
        
    def write_tag_end(self, tag):
        if tag in self.tag2html:
            self.out.write("</%s>" % self.tag2html[tag])
        else:
            self.out.write("</span>")



#=============================================================================
# RichText actions

class Action (object):
    def __init__(self):
        pass
    
    def do(self):
        pass
    
    def undo(self):
        pass


class InsertAction (Action):
    def __init__(self, richtext, pos, text, length):
        Action.__init__(self)
        self.richtext = richtext
        self.textbuffer = richtext.textbuffer
        self.pos = pos
        self.text = text
        self.length = length
        
    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.pos)
        self.textbuffer.place_cursor(start)
        self.textbuffer.insert_at_cursor(self.text)
    
    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.pos)
        end = self.textbuffer.get_iter_at_offset(self.pos + self.length)
        self.textbuffer.place_cursor(start)
        self.textbuffer.delete(start, end)


class DeleteAction (Action):
    def __init__(self, richtext, start_offset, end_offset, text,
                 cursor_offset):
        Action.__init__(self)
        self.richtext = richtext
        self.textbuffer = richtext.textbuffer
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.text = text
        self.cursor_offset = cursor_offset
        self.contents = []
    

    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.textbuffer.place_cursor(start)
        self.textbuffer.delete(start, end)

    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        
        self.textbuffer.begin_user_action()
        insert_buffer_contents(self.richtext, start, self.contents)
        cursor = self.textbuffer.get_iter_at_offset(self.cursor_offset)
        self.textbuffer.place_cursor(cursor)
        self.textbuffer.end_user_action()
    
    def record_range(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.contents = list(iter_buffer(self.textbuffer, start, end))



class InsertChildAction (Action):
    def __init__(self, richtext, pos, anchor):
        Action.__init__(self)
        self.richtext = richtext
        self.textbuffer = richtext.textbuffer
        self.pos = pos
        self.anchor = anchor
        self.child = None
    
    def do(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)
        self.anchor = self.textbuffer.create_child_anchor(it)
        self.child = self.child.get_owner().refresh()
        self.richtext.add_child_at_anchor(self.child, self.anchor)

    
    def undo(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)
        self.anchor = it.get_child_anchor()
        self.child = self.anchor.get_widgets()[0]
        it2 = it.copy()
        it2.forward_char()
        self.textbuffer.delete(it, it2)


class TagAction (Action):
    def __init__(self, richtext, tag, start_offset, end_offset, applied):
        Action.__init__(self)
        self.richtext = richtext
        self.textbuffer = richtext.textbuffer
        self.tag = tag
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.applied = applied
        
    
    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        if self.applied:
            self.textbuffer.apply_tag(self.tag, start, end)
        else:
            self.textbuffer.remove_tag(self.tag, start, end)

    
    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        if self.applied:
            self.textbuffer.remove_tag(self.tag, start, end)
        else:
            self.textbuffer.apply_tag(self.tag, start, end)


#=============================================================================
# RichText child objects


class RichTextChild (object):
    def __init__(self):
        self.child = None
    
    def get_child(self):
        return self.child
    
    def refresh(self):
        return self.child


class BaseChild (object):
    def __init__(self):
        self.owner = None
        
    def set_owner(self, owner):
        self.owner = owner
    
    def get_owner(self):
        return self.owner    
    

class BaseImage (gtk.Image, BaseChild):
    def __init__(self, *args, **kargs):
        gtk.Image.__init__(self, *args, **kargs)
        BaseChild.__init__(self)


class RichTextImage (RichTextChild):
    def __init__(self):
        RichTextChild.__init__(self)
        self.child = BaseImage()
        self.child.set_owner(self)
        self.child.connect("destroy", self.on_image_destroy)
        self.pixbuf = None
    
    
    def set_from_file(self, filename):
        self.child.set_from_file(filename)
        self.pixbuf = self.child.get_pixbuf()
    
    
    def refresh(self):
        if self.child == None:
            self.child = BaseImage()
            self.child.set_owner(self)
            self.child.set_from_pixbuf(self.pixbuf)
            self.child.show()
            self.child.connect("destroy", self.on_image_destroy)
        return self.child
        
    
    def on_image_destroy(self, widget):
        self.child = None
        

#=============================================================================
# RichText class

class RichTextView (gtk.TextView):

    def __init__(self):
        gtk.TextView.__init__(self)
        self.textbuffer = self.get_buffer()
        self.undo_stack = UndoStack()
        
        # signals
        self.textbuffer.connect("mark-set", self.on_mark_set)
        self.textbuffer.connect("insert-text", self.on_insert_text)
        self.textbuffer.connect("delete-range", self.on_delete_range)
        self.textbuffer.connect("insert-pixbuf", self.on_insert_pixbuf)
        self.textbuffer.connect("insert-child-anchor", self.on_insert_child_anchor)

        self.insertid = self.textbuffer.connect("changed", self.on_changed)
        self.textbuffer.connect("begin_user_action", self.on_begin_user_action)
        self.textbuffer.connect("begin_user_action", self.on_end_user_action)
        self.textbuffer.connect("apply-tag", self.on_apply_tag)
        self.textbuffer.connect("remove-tag", self.on_remove_tag)
        
        self.insert_mark = None
        self.next_action = None
        self.current_tags = []
        
        # font tags
        self.tag_table = self.textbuffer.get_tag_table()
        self.bold_tag = self.textbuffer.create_tag("Bold", weight=pango.WEIGHT_BOLD)
        self.italic_tag = self.textbuffer.create_tag("Italic", style=pango.STYLE_ITALIC)
        self.underline_tag = self.textbuffer.create_tag("Underline", underline=pango.UNDERLINE_SINGLE)
        self.family_tags = set()
        self.size_tags = set()
        
        self.html_buffer = HtmlBuffer()
        
        self.html_buffer.add_tag(self.bold_tag, "b")
        self.html_buffer.add_tag(self.italic_tag, "i")
        self.html_buffer.add_tag(self.underline_tag, "u")
        
        
        # TESTING        
        self.textbuffer.insert_at_cursor("hello")        
        #self.p = gtk.gdk.pixbuf_new_from_file("bitmaps/copy.xpm")
        #it = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
        #self.textbuffer.insert_pixbuf(it, self.p)
        
        self.image = RichTextImage()
        self.image.set_from_file("bitmaps/zebra.xpm")
        self.insert_image(self.image)
        
        self.textbuffer.insert_at_cursor("hello")
        
        image = gtk.Image()
        image.set_from_file("bitmaps/zebra.xpm")        
        #self.insert_image(image)
    
    
    #==================================================================
    # Callbacks
    
    
    def on_mark_set(self, textbuffer, it, mark):
        """Callback for mark movement"""
        
        if mark.get_name() == "insert":
            self.current_tags = []
            
            # update UI for current fonts
            self.on_update_bold(it.has_tag(self.bold_tag))
            self.on_update_italic(it.has_tag(self.italic_tag))
            self.on_update_underline(it.has_tag(self.underline_tag))
            # TODO: add size and family
    
    
    def on_insert_text(self, textbuffer, it, text, length):
        """Callback for text insert"""
        
        # start new action
        self.next_action = InsertAction(self, it.get_offset(), text, length)
        self.insert_mark = self.textbuffer.create_mark(None, it, True)

    def on_delete_range(self, textbuffer, start, end):
        """Callback for delete range"""
    
        # start next action
        self.next_action = DeleteAction(self, start.get_offset(), 
                                        end.get_offset(),
                                        start.get_slice(end),
                                        self.textbuffer.get_iter_at_mark(
                                            self.textbuffer.get_insert()).
                                                get_offset())
        self.next_action.record_range()
        
    
    def on_insert_pixbuf(self, textbuffer, it, pixbuf):
        """Callback for inserting a pixbuf"""
        pass
    
    
    def on_insert_child_anchor(self, textbuffer, it, anchor):
        """Callback for inserting a child anchor"""
        self.next_action = InsertChildAction(self, it.get_offset(), anchor)
    
    def on_apply_tag(self, textbuffer, tag, start, end):
        """Callback for tag apply"""
        
        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), True)
        self.undo_stack.do(action.do, action.undo, False)
    
    def on_remove_tag(self, textbuffer, tag, start, end):
        """Callback for tag remove"""
    
        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), False)
        self.undo_stack.do(action.do, action.undo, False)
    
    
    def on_changed(self, textbuffer):
        """Callback for buffer change"""
    
        # apply current style to inserted text
        if isinstance(self.next_action, InsertAction):
            if len(self.current_tags) > 0:
                it = self.textbuffer.get_iter_at_mark(self.insert_mark)
                it2 = it.copy()
                it2.forward_chars(self.next_action.length)

                for tag in self.current_tags:
                    self.textbuffer.apply_tag(tag, it, it2)

                self.textbuffer.delete_mark(self.insert_mark)
                self.insert_mark = None
        
        
        if self.next_action:
            self.undo_stack.do(self.next_action.do, self.next_action.undo, False)
            self.next_action = None
    
    #==================================================================
    # UI Updating for fonts
    
    def on_update_bold(self, enabled):
        pass

    def on_update_italic(self, enabled):
        pass

    def on_update_underline(self, enabled):
        pass

    
    #==================================================================
    # Actions
    
    def save(self):
        out = open("notes.html", "w")
        self.write_buffer(out)
        out.close()
    
    
    def load(self):
        self.textbuffer.begin_user_action()    
        start = self.textbuffer.get_start_iter()
        end = self.textbuffer.get_end_iter()
        self.textbuffer.remove_all_tags(start, end)
        self.textbuffer.delete(start, end)
        self.html_buffer.read(self, open("notes.html", "r"))
        self.textbuffer.end_user_action()


    def toggle_tag(self, tag):
        self.textbuffer.begin_user_action()
        it = self.textbuffer.get_selection_bounds()
        
        if len(it) == 0:
            if tag not in self.current_tags:
                self.current_tags.append(tag)
            else:
                self.current_tags.remove(tag)
        else:
            if not it[0].has_tag(tag):
                self.clear_font_tags(tag, it[0], it[1])
                self.textbuffer.apply_tag(tag, it[0], it[1])
            else:
                self.textbuffer.remove_tag(tag, it[0], it[1])
        
        self.textbuffer.end_user_action()

    def apply_tag(self, tag):
        self.textbuffer.begin_user_action()    
        it = self.textbuffer.get_selection_bounds()
        
        if len(it) == 0:
            if tag not in self.current_tags:
                self.current_tags.append(tag)
        else:
            self.clear_font_tags(tag, it[0], it[1])
            self.textbuffer.apply_tag(tag, it[0], it[1])
        self.textbuffer.end_user_action()


    def remove_tag(self, tag):
        self.textbuffer.begin_user_action()
        it = self.textbuffer.get_selection_bounds()
        
        if len(it) == 0:
            if tag in self.current_tags:
                self.current_tags.remove(tag)
        else:
            self.textbuffer.remove_tag(tag, it[0], it[1])
        self.textbuffer.end_user_action()
    
    
    def clear_font_tags(self, tag, start, end):
        
        # remove other family tags        
        if tag in self.family_tags:
            for tag2 in self.family_tags:
                self.textbuffer.remove_tag(tag2, start, end)
        
        # remove other size tags                    
        if tag in self.size_tags:
            for tag2 in self.size_tags:
                self.textbuffer.remove_tag(tag2, start, end)
    
    def insert_image(self, image):
        self.textbuffer.begin_user_action()
        it = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
        anchor = self.textbuffer.create_child_anchor(it)
        self.add_child_at_anchor(image.get_child(), anchor)
        self.textbuffer.end_user_action()
    
    
    def write_buffer(self, out):
        """Write buffer to output stream"""
        
        self.html_buffer.set_output(out)
        self.html_buffer.write(self)
        
    #===========================================================
    # Callbacks for Font 

    def on_bold(self, widget, event):
        self.toggle_tag(self.bold_tag)
        
    def on_italic(self, widget, event):
        self.toggle_tag(self.italic_tag)
    
    def on_underline(self, widget, event):
        self.toggle_tag(self.underline_tag)
    
    
    def on_font_set(self, widget):
        family, mods, size = self.parse_font(widget.get_font_name())
        
        # apply family tag
        self.apply_tag(self.lookup_family_tag(family))
        
        # apply size
        self.apply_tag(self.lookup_size_tag(size))
        
        # apply mods
        for mod in mods:
            self.apply_tag(self.tag_table.lookup(mod))
        
        # disable mods not given
        for mod in ["Bold", "Italic", "Underline"]:
            if mod not in mods:
                self.remove_tag(self.tag_table.lookup(mod))
    
    #===========================================================
    # Font management
    
    def lookup_family_tag(self, family):
        tag = self.tag_table.lookup(family)
        if tag == None:
            tag = self.textbuffer.create_tag(family, family=family)
            self.add_family_tag(tag)
        return tag
    
    def lookup_size_tag(self, size):
        sizename = "size %d" % size
        tag = self.tag_table.lookup(sizename)
        if tag == None:
            tag = self.textbuffer.create_tag(sizename, size_points=size)
            self.add_size_tag(tag)
        return tag
    
    def add_family_tag(self, tag):
        self.html_buffer.add_family_tag(tag)
        self.family_tags.add(tag)        
    
    def add_size_tag(self, tag):
        self.html_buffer.add_size_tag(tag)
        self.size_tags.add(tag)
    

    def parse_font(self, fontstr):
        tokens = fontstr.split(" ")
        size = int(tokens.pop())
        mods = []
        
        while tokens[-1] in ["Bold", "Italic", "Underline"]:
            mods.append(tokens.pop())

        return " ".join(tokens), mods, size
    
    
    #=========================================
    # undo/redo methods
    
    def undo(self):
        """Undo the last action in the RichTextView"""
        self.undo_stack.undo()
        
    def redo(self):
        """Redo the last action in the RichTextView"""    
        self.undo_stack.redo()    
    
    def on_begin_user_action(self, textbuffer):
        """Begin a composite undo/redo action"""
        self.undo_stack.begin_action()

    def on_end_user_action(self, textbuffer):
        """End a composite undo/redo action"""
        self.undo_stack.end_action()





