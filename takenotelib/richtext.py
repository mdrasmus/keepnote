"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    General rich text editor that saves to HTML
"""



# python imports
import sys, os, tempfile, re
from HTMLParser import HTMLParser


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
import takenotelib as takenote
from takenotelib.undo import UndoStack


# constants
MIME_TAKENOTE = "application/x-takenote"

#=============================================================================
# functions for iterating and inserting into textbuffers

def iter_buffer_contents(textbuffer, start=None, end=None):
    """Iterate over the items of a textbuffer"""
    
    if start == None:
        it = textbuffer.get_start_iter()
    else:
        it = start.copy()
    last = it.copy()

    if end == None:
        end = textbuffer.get_end_iter()


    # yield opening tags at begining of region
    for tag in it.get_tags():
        yield ("begin", it, tag)
    
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
                yield ("text", it2, it2.get_text(stop))
                break
            
            a, b = ret
            anchor = a.get_child_anchor()
            
            # yield text in between tags
            yield ("text", it2, it2.get_text(a))
            if anchor != None:
                yield ("anchor", a, (anchor, anchor.get_widgets()))
            else:
                yield ("pixbuf", a, a.get_pixbuf())
            it2 = b
        
        # stop iterating if we have pasted end of region
        if it.get_offset() > end.get_offset():
            break
        
        # yield closing tags
        for tag in it.get_toggled_tags(False):
            yield ("end", it, tag)

        # yield opening tags
        for tag in it.get_toggled_tags(True):
            yield ("begin", it, tag)
        
        last = it.copy()
        
        if it.equal(end):
            break
    
    # yield tags that have not been closed yet
    toggled = set(end.get_toggled_tags(False))
    for tag in end.get_tags():
        if tag not in toggled:
            yield ("end", end, tag)


def buffer_contents_iter_to_offset(contents):
    """Converts to iters of a content list to offsets"""
    
    for kind, it, param in contents:
        yield (kind, it.get_offset(), param)
    

def normalize_tags(items):
    """Normalize open and close tags to ensure proper nesting"""

    open_stack = []

    for item in items:
        kind, it, param = item
        if kind == "begin":
            open_stack.append(param)
            yield item

        elif kind == "end":

            # close any open out of order tags
            reopen_stack = []
            while param != open_stack[-1]:
                reopen_stack.append(open_stack.pop())
                tag2 = reopen_stack[-1]
                yield ("end", it, tag2)

            # close current tag
            open_stack.pop()
            yield item

            # reopen tags
            for tag2 in reversed(reopen_stack):
                open_stack.append(tag2)
                yield ("begin", it, tag2)

        else:
            yield item


def insert_buffer_contents(textview, pos, contents):
    """Insert a content list into a textview"""
    
    textbuffer = textview.get_buffer()
    
    textbuffer.place_cursor(pos)
    tags = {}
    
    # make sure all tags are removed on first text/anchor insert
    first_insert = True
    
    for item in contents:
        kind, offset, param = item
        
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
            child = param[1][0].get_owner().copy().get_child()
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


def buffer_contents_apply_tags(textview, contents):
    """Apply tags into a textview"""
    
    textbuffer = textview.get_buffer()
    
    tags = {}
    
    # make sure all tags are removed on first text/anchor insert
    first_insert = True
    
    for item in contents:
        kind, offset, param = item
        
        if kind == "begin":
            tags[param] = textbuffer.get_iter_at_offset(offset)
            
        elif kind == "end":
            start = tags[param]
            end = textbuffer.get_iter_at_offset(offset)
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
        self.newline = False
        
        self.size_tags = set()
        self.family_tags = set()
        self.justify_tags = set()
        self.justify2tag = {}
        self.tag2justify = {}
        
        self.tag_stack = []
        self.richtext = None
        self.buffer = None
        
        self.entity_char_map = [("&", "amp"),
                                (">", "gt"),
                                ("<", "lt"),
                                (" ", "nbsp")]
        self.entity2char = {}
        for ch, name in self.entity_char_map:
            self.entity2char[name] = ch
        
        self.charref2char = {"09": "\t"}
        
        
        
    
    def set_output(self, out):
        self.out = out
    
    
    def add_tag(self, tag, html_name):
        self.tag2html[tag] = html_name
        self.html2tag[html_name] = tag
    
    
    def add_size_tag(self, tag):
        self.size_tags.add(tag)
    
    
    def add_family_tag(self, tag):
        self.family_tags.add(tag)
    
    
    def add_justify_tag(self, tag, justify):
        self.justify_tags.add(tag)
        self.tag2justify[tag] = justify
        self.justify2tag[justify] = tag
    
    def read(self, richtext, infile):
        self.richtext = richtext
        self.buffer = richtext.textbuffer
        
        for line in infile:
            self.feed(line)
        self.close()
        
        self.buffer.place_cursor(self.buffer.get_start_iter())
    
    
    def handle_starttag(self, tag, attrs):
        self.newline = False
        if tag in ("html", "body"):
            return
    
        mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), True)
        self.tag_stack.append((tag, attrs, mark))


    def handle_endtag(self, tag):
        self.newline = False
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
            self.newline = True
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
        
        elif htmltag == "div":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("text-align"):
                        align = value.split(":")[1].strip()
                        tag = self.justify2tag[align]
                        
                    else:
                        raise Exception("unknown style '%s'" % value)
                else:
                    raise Exception("unknown attr key '%s'" % key)
        
        elif htmltag == "img":
            
            for key, value in attrs:
                if key == "src":
                    img = RichTextImage()
                    img.set_filename(value)
                    self.richtext.insert_image(img)
                    pass
                else:
                    Exception("unknown attr key '%s'" % key)
            return
        
        else:
            raise Exception("WARNING: unhandled tag '%s'" % htmltag)
            
        start = self.buffer.get_iter_at_mark(mark)
        self.buffer.apply_tag(tag, start, self.buffer.get_end_iter())
        self.buffer.delete_mark(mark)

    def handle_data(self, data):
        if self.newline:
            data = re.sub("\n[\n ]*", "", data)
            self.newline = False
        else:
            data = re.sub("[\n ]+", " ", data)
        self.buffer.insert(self.buffer.get_end_iter(), data)
    
    def handle_entityref(self, name):
        self.buffer.insert(self.buffer.get_end_iter(),
                           self.entity2char.get(name, ""))
    
    def handle_charref(self, name):
        self.buffer.insert(self.buffer.get_end_iter(),
                           self.charref2char.get(name, ""))
        
    
    def write(self, richtext):
        textbuffer = richtext.textbuffer
        
        self.out.write("<html><body>")
        
        for kind, it, param in normalize_tags(iter_buffer_contents(textbuffer)):
            if kind == "text":
                text = param
                text = text.replace("&", "&amp;")
                text = text.replace(">", "&gt;")
                text = text.replace("<", "&lt;")
                text = text.replace("\n", "<br/>\n")
                text = text.replace("\t", "&#09;")
                text = text.replace("  ", " &nbsp;")
                self.out.write(text)
            
            elif kind == "begin":
                tag = param
                self.write_tag_begin(tag)
                
            elif kind == "end":
                tag = param
                self.write_tag_end(tag)
            
            elif kind == "anchor":
                for widget in param[1]:
                    child = widget.get_owner()
                    if isinstance(child, RichTextImage):
                        self.out.write("<img src=\"%s\"/>" % child.get_filename())
                    else:
                        # warning
                        print "unknown child element", widget
            
            elif kind == "pixbuf":
                self.out.write("")
        
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
            elif tag in self.justify_tags:
                            
                self.out.write("<div style='text-align: %s'>" % 
                          self.tag2justify[tag])
            else:
                raise Exception("unknown tag")
                
        
    def write_tag_end(self, tag):
        if tag in self.tag2html:
            self.out.write("</%s>" % self.tag2html[tag])
        elif tag in self.justify_tags:
            self.out.write("</div>")
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


class ModifyAction (Action):
    def __init__(self, textbuffer):
        self.textbuffer = textbuffer
        self.was_modified = False
    
    def do(self):
        self.was_modified = self.textbuffer.is_modified()
        self.textbuffer.modify()
    
    def undo(self):
        if not self.was_modified:
            self.textbuffer.unmodify()
        

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
        self.record_range()
    

    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.textbuffer.place_cursor(start)
        self.record_range()
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
        self.contents = list(buffer_contents_iter_to_offset(
            iter_buffer_contents(self.textbuffer, start, end)))



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
        self.child = self.child.copy()
        self.richtext.add_child_at_anchor(self.child.get_child(), self.anchor)
        

    
    def undo(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)
        self.anchor = it.get_child_anchor()
        self.child = self.anchor.get_widgets()[0].get_owner()
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
        self.contents = []
        self.record_range()
        
    
    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.record_range()
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
        buffer_contents_apply_tags(self.richtext, self.contents)
        
    
    def record_range(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.contents = filter(lambda (kind, it, param): 
            kind in ("begin", "end") and param == self.tag,
            buffer_contents_iter_to_offset(
                iter_buffer_contents(self.textbuffer, start, end)))


#=============================================================================
# RichText child objects


class RichTextChild (object):
    def __init__(self):
        self.child = None
    
    def get_child(self):
        return self.child
    
    def refresh(self):
        return self.child
    
    def copy(slef):
        return RichTextChild()


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
        self.filename = None
        self.child = BaseImage()
        self.child.set_owner(self)
        self.child.connect("destroy", self.on_image_destroy)
        self.pixbuf = None
    
    def set_filename(self, filename):
        self.filename = filename
    
    def get_filename(self):
        return self.filename
    
    def set_from_file(self, filename):
        if self.filename == None:
            self.filename = os.path.basename(filename)
        self.child.set_from_file(filename)
        self.pixbuf = self.child.get_pixbuf()
    
    
    def set_from_pixbuf(self, pixbuf, filename=None):
        if filename != None:
            self.filename = filename
        self.child.set_from_pixbuf(pixbuf)
        self.pixbuf = pixbuf
    
    def refresh(self):
        if self.child == None:
            self.child = BaseImage()
            self.child.set_owner(self)
            self.child.set_from_pixbuf(self.pixbuf)
            self.child.show()
            self.child.connect("destroy", self.on_image_destroy)
        return self.child
        
    def copy(self):
        img = RichTextImage()
        img.filename = self.filename
        img.child.set_from_pixbuf(self.pixbuf)
        img.pixbuf = self.pixbuf
        img.child.show()
        return img
    
    def on_image_destroy(self, widget):
        self.child = None
        

#=============================================================================
# RichText classes

class RichTextBuffer (gtk.TextBuffer):
    def __init__(self, textview=None):
        gtk.TextBuffer.__init__(self)
        self.clipboard_contents = None
        self.textview = textview
        self._modified = False

    
    def modify(self):
        self._modified = True
    
    def unmodify(self):
        self._modified = False
        
    
    def is_modified(self):
        return self._modified
        
    
    def set_textview(self, textview):
        self.textview = textview
    
    def get_textview(self):
        return self.textview

    def copy_clipboard(self, clipboard):
        """Callback for copy event"""
        
        #targets = [(MIME_TAKENOTE, gtk.TARGET_SAME_APP | gtk.TARGET_SAME_WIDGET, 0),
        #           ("application/x-gtk-text-buffer-rich-text", gtk.TARGET_SAME_APP, 0),
        #           ("GTK_TEXT_BUFFER_CONTENTS", gtk.TARGET_SAME_APP, -1),
        #           ("text/plain", 0, -3)]
        
        targets = [(MIME_TAKENOTE, gtk.TARGET_SAME_APP, -3),
                   ("text/plain", 0, -3),
                   ("text/plain;charset=utf-8", 0, -3),
                   ("text/plain;charset=UTF-8", 0, -3),
                   ("UTF8_STRING", 0, -3),
                   ("STRING", 0, -3),
                   ("COMPOUND_TEXT", 0, -3),
                   ("TEXT", 0, -3)]
        
        sel = self.get_selection_bounds()
        if sel:
            start, end = sel
            contents = list(iter_buffer_contents(self, start, end))
            text = start.get_text(end)
            clipboard.set_with_data(targets, self.get_selection_data, 
                                    self.clear_selection_data,
                                    (contents, text))

    def cut_clipboard(self, clipboard, default_editable):
        """Callback for cut event"""
        
        self.copy_clipboard(clipboard)
        self.delete_selection(False, default_editable)

    
    def paste_clipboard(self, clipboard, override_location, default_editable):
        """Callback for paste event"""
        
        if clipboard.wait_is_target_available(MIME_TAKENOTE):
            clipboard.request_contents(MIME_TAKENOTE, self.do_paste)
        else:
            clipboard.request_text(self.do_paste_text)
        
    
    def do_paste_text(self, clipboard, text, data):
        self.begin_user_action()
        self.delete_selection(False, True)
        self.insert_at_cursor(text)
        self.end_user_action()
    
    
    def do_paste(self, clipboard, selection_data, data):
        assert self.clipboard_contents != None
        
        self.begin_user_action()
        it = self.get_iter_at_mark(self.get_insert())
        insert_buffer_contents(self.textview, it, self.clipboard_contents)
        self.end_user_action()
    
    
    def get_selection_data(self, clipboard, selection_data, info, data):
        """Callback for when Clipboard needs selection data"""
        
        self.clipboard_contents = data[0]
        
        
        if MIME_TAKENOTE in selection_data.target:
            # set rich text
            selection_data.set(MIME_TAKENOTE, 8, "<takenote>")
        else:
            # set plain text        
            selection_data.set_text(data[1])

    
    def clear_selection_data(self, clipboard, data):
        self.clipboard_contents = None

    

class RichTextView (gtk.TextView):

    def __init__(self):
        gtk.TextView.__init__(self, RichTextBuffer(self))
        self.textbuffer = self.get_buffer()
        self.undo_stack = UndoStack()
        self.set_wrap_mode(gtk.WRAP_WORD)
        
        self.font_callback = None
        self.ignore_font_upate = False
        
        # signals
        self.textbuffer.connect("mark-set", self.on_mark_set)
        self.textbuffer.connect("insert-text", self.on_insert_text)
        self.textbuffer.connect("delete-range", self.on_delete_range)
        self.textbuffer.connect("insert-pixbuf", self.on_insert_pixbuf)
        self.textbuffer.connect("insert-child-anchor", self.on_insert_child_anchor)
        self.textbuffer.connect("apply-tag", self.on_apply_tag)
        self.textbuffer.connect("remove-tag", self.on_remove_tag)        
        self.insertid = self.textbuffer.connect("changed", self.on_changed)
        self.textbuffer.connect("begin_user_action", self.on_begin_user_action)
        self.textbuffer.connect("end_user_action", self.on_end_user_action)
        #self.connect("populate-popup", self.on_popup)
        
        self.connect("copy-clipboard", self.on_copy)
        self.connect("cut-clipboard", self.on_cut)
        self.connect("paste-clipboard", self.on_paste)
        
        self.set_property("right-margin", 5)
        self.set_property("left-margin", 5)
        
        self.insert_mark = None
        self.next_action = None
        self.current_tags = []
        self.first_menu = True
        
        # font tags
        self.tag_table = self.textbuffer.get_tag_table()
        
        self.bold_tag = self.textbuffer.create_tag("Bold", weight=pango.WEIGHT_BOLD)
        self.italic_tag = self.textbuffer.create_tag("Italic", style=pango.STYLE_ITALIC)
        self.underline_tag = self.textbuffer.create_tag("Underline", underline=pango.UNDERLINE_SINGLE)
        
        self.left_tag = self.textbuffer.create_tag("Left", justification=gtk.JUSTIFY_LEFT)
        self.center_tag = self.textbuffer.create_tag("Center", justification=gtk.JUSTIFY_CENTER)
        self.right_tag = self.textbuffer.create_tag("Right", justification=gtk.JUSTIFY_RIGHT)        
        
        self.justify_tags = set([self.left_tag, self.center_tag, self.right_tag])
        self.family_tags = set()
        self.size_tags = set()
        
        
        # initialize HTML buffer
        self.html_buffer = HtmlBuffer()
        
        self.html_buffer.add_tag(self.bold_tag, "b")
        self.html_buffer.add_tag(self.italic_tag, "i")
        self.html_buffer.add_tag(self.underline_tag, "u")
        self.html_buffer.add_justify_tag(self.left_tag, "left")
        self.html_buffer.add_justify_tag(self.center_tag, "center")
        self.html_buffer.add_justify_tag(self.right_tag, "right")
        
        # requires new pygtk
        #self.textbuffer.register_serialize_format(MIME_TAKENOTE, 
        #                                          self.serialize, None)
        #self.textbuffer.register_deserialize_format(MIME_TAKENOTE, 
        #                                            self.deserialize, None)


        
    """
    def on_popup(self, textview, menu):
        return
        self.first_menu = False
        menu.foreach(lambda item: menu.remove(item))

        # Create the menu item
        copy_item = gtk.MenuItem("Copy")
        copy_item.connect("activate", self.on_copy)
        menu.add(copy_item)
        
        accel_group = menu.get_accel_group()
        print "accel", accel_group
        if accel_group == None:
            accel_group = gtk.AccelGroup()
            menu.set_accel_group(accel_group)
            print "get", menu.get_accel_group()


        # Now add the accelerator to the menu item. Note that since we created
        # the menu item with a label the AccelLabel is automatically setup to 
        # display the accelerators.
        copy_item.add_accelerator("activate", accel_group, ord("C"),
                                  gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        copy_item.show()                                  
    """
            
           
    
    def serialize(self, register_buf, content_buf, start, end, data):
        print "serialize", content_buf
        self.a = u"SERIALIZED"
        return self.a 
    
    
    def deserialize(self, register_buf, content_buf, it, data, create_tags, udata):
        print "deserialize"
     
    
    def on_copy(self, textview):
        clipboard = self.get_clipboard(selection="CLIPBOARD") #gtk.clipboard_get(gdk.SELECTION_CLIPBOARD)
        self.textbuffer.copy_clipboard(clipboard)
        self.stop_emission('copy-clipboard')
    
    def on_cut(self, textview):
        clipboard = self.get_clipboard(selection="CLIPBOARD") #gtk.clipboard_get(gdk.SELECTION_CLIPBOARD)
        self.textbuffer.cut_clipboard(clipboard, self.get_editable())
        self.stop_emission('cut-clipboard')
    
    def on_paste(self, textview):
        clipboard = self.get_clipboard(selection="CLIPBOARD") #gtk.clipboard_get(gdk.SELECTION_CLIPBOARD)
        self.textbuffer.paste_clipboard(clipboard, None, self.get_editable())
        self.stop_emission('paste-clipboard')

    
    
    #==================================================================
    # Callbacks
    
    
    def on_mark_set(self, textbuffer, it, mark):
        """Callback for mark movement"""
        
        if mark.get_name() == "insert":
            self.current_tags = []
            
            # update UI for current fonts
            self.on_update_font()
            
    
    
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
        
    
    def on_insert_pixbuf(self, textbuffer, it, pixbuf):
        """Callback for inserting a pixbuf"""
        pass
    
    
    def on_insert_child_anchor(self, textbuffer, it, anchor):
        """Callback for inserting a child anchor"""
        self.next_action = InsertChildAction(self, it.get_offset(), anchor)
    
    def on_apply_tag(self, textbuffer, tag, start, end):
        """Callback for tag apply"""
        
        self.textbuffer.begin_user_action()
        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), True)
        self.undo_stack.do(action.do, action.undo, False)
        action = ModifyAction(self.textbuffer)
        self.undo_stack.do(action.do, action.undo)
        self.textbuffer.end_user_action()
    
    def on_remove_tag(self, textbuffer, tag, start, end):
        """Callback for tag remove"""
    
        self.textbuffer.begin_user_action()
        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), False)
        self.undo_stack.do(action.do, action.undo, False)
        action = ModifyAction(self.textbuffer)
        self.undo_stack.do(action.do, action.undo)
        self.textbuffer.end_user_action()
    
    
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
            self.textbuffer.begin_user_action()        
            self.undo_stack.do(self.next_action.do, self.next_action.undo, False)
            self.next_action = None
            action = ModifyAction(self.textbuffer)
            self.undo_stack.do(action.do, action.undo)
            
            self.textbuffer.end_user_action()
    


    
    #==================================================================
    # File I/O
    
    def save(self, filename):
        path = os.path.dirname(filename)
        self.save_images(path)
    
        out = open(filename, "w")
        self.html_buffer.set_output(out)
        self.html_buffer.write(self)
        out.close()
        
        self.textbuffer.unmodify()
    
    
    def load(self, filename):
        self.textbuffer.begin_user_action()
        
        start = self.textbuffer.get_start_iter()
        end = self.textbuffer.get_end_iter()
        self.textbuffer.remove_all_tags(start, end)
        self.textbuffer.delete(start, end)
        self.html_buffer.read(self, open(filename, "r"))
        
        path = os.path.dirname(filename)
        self.load_images(path)
        
        self.textbuffer.end_user_action()
        self.undo_stack.reset()
        self.enable()
        
        self.textbuffer.unmodify()
    
    
    def enable(self):
        self.set_sensitive(True)
    
    
    def disable(self):
        
        start = self.textbuffer.get_start_iter()
        end = self.textbuffer.get_end_iter()
        self.textbuffer.remove_all_tags(start, end)
        self.textbuffer.delete(start, end)
        self.undo_stack.reset()
        self.set_sensitive(False)
        
        self.textbuffer.unmodify()
        
    
    def load_images(self, path):
        
        for kind, it, param in iter_buffer_contents(self.textbuffer):
            if kind == "anchor":
                anchor, widgets = param
                
                for widget in widgets:
                    child = widget.get_owner()
                    
                    if isinstance(child, RichTextImage):
                        filename = os.path.join(path, child.get_filename())
                        child.set_from_file(filename)
                        child.get_child().show()

    def save_images(self, path):
        for kind, it, param in iter_buffer_contents(self.textbuffer):
            if kind == "anchor":
                anchor, widgets = param
                
                for widget in widgets:
                    child = widget.get_owner()
                    
                    if isinstance(child, RichTextImage):
                        filename = os.path.join(path, child.get_filename())
                        
                        f, ext = os.path.splitext(filename)
                        ext = ext.replace(".", "")
                        if ext == "jpg":
                            ext = "jpeg"
                        
                        child.pixbuf.save(filename, ext) #, {"quality":"100"})

    
    def is_modified(self):
        return self.textbuffer.is_modified()
                        
    
    #===========================================================
    # Actions
        
    def insert_image(self, image, filename="image.jpg"):
        """Inserts an image into the textbuffer"""
                
        self.textbuffer.begin_user_action()
        
        it = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
        anchor = self.textbuffer.create_child_anchor(it)
        self.add_child_at_anchor(image.get_child(), anchor)
        image.get_child().show()
        
        self.textbuffer.end_user_action()
        
        if image.get_filename() == None:
            filename, ext = os.path.splitext(filename)
            filenames = self.get_image_filenames()
            filename = takenote.get_unique_filename_list(filenames, filename, ext)
            image.set_filename(filename)
    
    
    def get_image_filenames(self):
        filenames = []
    
        for kind, it, param in iter_buffer_contents(self.textbuffer):
            if kind == "anchor":
                anchor, widgets = param
                
                for widget in widgets:
                    child = widget.get_owner()
                    
                    if isinstance(child, RichTextImage):
                        filenames.append(child.get_filename())
        
        return filenames
        
    
    
    #==============================================================
    # Tag manipulation    

    def toggle_tag(self, tag):
        self.textbuffer.begin_user_action()
        it = self.textbuffer.get_selection_bounds()
        
        if len(it) == 0:
            if tag not in self.current_tags:
                self.clear_current_font_tags(tag)
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
                self.clear_current_font_tags(tag)
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
        
        # remove other justify tags
        if tag in self.justify_tags:
            for tag2 in self.justify_tags:
                self.textbuffer.remove_tag(tag2, start, end)
        
        # remove other family tags        
        if tag in self.family_tags:
            for tag2 in self.family_tags:
                self.textbuffer.remove_tag(tag2, start, end)
        
        # remove other size tags                    
        if tag in self.size_tags:
            for tag2 in self.size_tags:
                self.textbuffer.remove_tag(tag2, start, end)

    def clear_current_font_tags(self, tag):
        
        # remove other justify tags
        if tag in self.justify_tags:
            for tag2 in self.justify_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)
        
        # remove other family tags        
        if tag in self.family_tags:
            for tag2 in self.family_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)
        
        # remove other size tags                    
        if tag in self.size_tags:
            for tag2 in self.size_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)

        
    #===========================================================
    # Callbacks for Font 

    def on_bold(self):
        self.toggle_tag(self.bold_tag)
        
    def on_italic(self):
        self.toggle_tag(self.italic_tag)
    
    def on_underline(self):
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
    
    def on_left_justify(self):
        self.apply_tag(self.left_tag)
        
    def on_center_justify(self):
        self.apply_tag(self.center_tag)
    
    def on_right_justify(self):
        self.apply_tag(self.right_tag)
        
    
    #==================================================================
    # UI Updating for fonts
    
    def on_update_font(self):
        mods, justify = self.get_font()
        # TODO: add size and family
        
        if self.font_callback:
            self.font_callback(mods, justify)
    
    
    def get_font(self):
        it = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
        
        mods = {"bold":      self.bold_tag in self.current_tags or 
                             it.has_tag(self.bold_tag),
                "italic":    self.italic_tag in self.current_tags or 
                             it.has_tag(self.italic_tag),
                             
                "underline": self.underline_tag in self.current_tags or 
                             it.has_tag(self.underline_tag)}

        justify = "left"
        
        if self.center_tag in self.current_tags or \
           it.has_tag(self.center_tag):
            justify = "center"

        if self.right_tag in self.current_tags or \
           it.has_tag(self.right_tag):
            justify = "right"

        return mods, justify
        
    
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





