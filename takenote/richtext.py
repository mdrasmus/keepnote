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
import takenote
from takenote.undo import UndoStack


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


def insert_buffer_contents(textbuffer, pos, contents):
    """Insert a content list into a textview"""
    
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
            child = param[1][0].get_owner().copy()
            textbuffer.add_child_at_anchor(child, anchor)
            
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


def buffer_contents_apply_tags(textbuffer, contents):
    """Apply tags to a textbuffer"""
    
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

class HtmlError (StandardError):
    pass


class HtmlBuffer (HTMLParser):
    """Read and write HTML for a gtk.TextBuffer"""
    
    def __init__(self, out=None):
        HTMLParser.__init__(self)
    
        self.out = out
        self.tag2html = {}
        self.html2tag = {}
        self.newline = False        
        
        self.tag_stack = []
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
    
    
    def read(self, textbuffer, infile):
        self.buffer = textbuffer
        
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
        
        if self.tag_stack[-1][0] != tag:
            raise HtmlError("closing tag does not match opening tag")
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
                        tag = self.buffer.lookup_size_tag(size)
                        
                    elif value.startswith("font-family"):
                        family = value.split(":")[1].strip()
                        tag = self.buffer.lookup_family_tag(family)
                    
                    else:
                        raise HtmlError("unknown style '%s'" % value)
                else:
                    raise HtmlError("unknown attr key '%s'" % key)
        
        elif htmltag == "div":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("text-align"):
                        align = value.split(":")[1].strip()
                        if align == "left":
                            tag = self.buffer.left_tag
                        elif align == "center":
                            tag = self.buffer.center_tag
                        elif align == "right":
                            tag = self.buffer.right_tag
                        elif align == "justify":
                            tag = self.buffer.fill_tag
                        else:
                            raise HtmlError("unknown justification '%s'" % align)
                    else:
                        raise HtmlError("unknown style '%s'" % value)
                else:
                    raise HtmlError("unknown attr key '%s'" % key)
        
        elif htmltag == "img":
            
            for key, value in attrs:
                if key == "src":
                    img = RichTextImage()
                    img.set_filename(value)
                    self.buffer.insert_image(img)
                    pass
                else:
                    HtmlError("unknown attr key '%s'" % key)
            return
        
        else:
            raise HtmlError("WARNING: unhandled tag '%s'" % htmltag)
            
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
        self.buffer = richtext.textbuffer
        
        self.out.write("<html><body>")
        
        for kind, it, param in normalize_tags(iter_buffer_contents(self.buffer)):
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
                        #TODO:
                        print "unknown child element", widget
            
            elif kind == "pixbuf":
                self.out.write("")
        
        self.out.write("</body></html>")
        
    
    def write_tag_begin(self, tag):
        if tag in self.tag2html:
            self.out.write("<%s>" % self.tag2html[tag])
        else:
            if tag in self.buffer.size_tags:
                self.out.write("<span style='font-size: %dpt'>" % 
                          tag.get_property("size-points"))
            elif tag in self.buffer.family_tags:
                self.out.write("<span style='font-family: %s'>" % 
                          tag.get_property("family"))
            elif tag in self.buffer.justify_tags:
                if tag == self.buffer.left_tag:
                    text = "left"
                elif tag == self.buffer.center_tag:
                    text = "center"
                elif tag == self.buffer.right_tag:
                    text = "right"
                else:
                    text = "justify"
                self.out.write("<div style='text-align: %s'>" % text)
            else:
                raise HtmlError("unknown tag")
                
        
    def write_tag_end(self, tag):
        if tag in self.tag2html:
            self.out.write("</%s>" % self.tag2html[tag])
        elif tag in self.buffer.justify_tags:
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
        

# XXX: do I need to record current tags to properly redo insert?
class InsertAction (Action):
    def __init__(self, textbuffer, pos, text, length):
        Action.__init__(self)
        self.textbuffer = textbuffer
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
    def __init__(self, textbuffer, start_offset, end_offset, text,
                 cursor_offset):
        Action.__init__(self)
        self.textbuffer = textbuffer
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
        insert_buffer_contents(self.textbuffer, start, self.contents)
        cursor = self.textbuffer.get_iter_at_offset(self.cursor_offset)
        self.textbuffer.place_cursor(cursor)
        self.textbuffer.end_user_action()

    
    def record_range(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.contents = list(buffer_contents_iter_to_offset(
            iter_buffer_contents(self.textbuffer, start, end)))



class InsertChildAction (Action):
    def __init__(self, textbuffer, pos, anchor):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.pos = pos
        self.anchor = anchor
        self.child = None
        
    
    def do(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)
        self.anchor = self.textbuffer.create_child_anchor(it)
        self.child = self.child.copy()
        self.textbuffer.add_child_at_anchor(self.child, self.anchor)
        

    
    def undo(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)
        self.anchor = it.get_child_anchor()
        self.child = self.anchor.get_widgets()[0].get_owner()
        it2 = it.copy()
        it2.forward_char()
        self.textbuffer.delete(it, it2)
        


class TagAction (Action):
    def __init__(self, textbuffer, tag, start_offset, end_offset, applied):
        Action.__init__(self)
        self.textbuffer = textbuffer
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
        buffer_contents_apply_tags(self.textbuffer, self.contents)
        
    
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
    """Base class of all child objects in a RichTextView"""
    
    def __init__(self):
        self._widget = None
    
    def get_widget(self):
        return self._widget
    
    def refresh(self):
        return self._widget
    
    def copy(slef):
        return RichTextChild()


class BaseWidget (object):
    """This class is used to supplement widgets with a pointer back to the 
       owner RichTextChild object"""
    
    def __init__(self):
        self.owner = None
        
    def set_owner(self, owner):
        self.owner = owner
    
    def get_owner(self):
        return self.owner    
    

class BaseImage (gtk.Image, BaseWidget):
    """Subclasses gtk.Image to make an Image Widget that can be used within
       RichTextViewS"""

    def __init__(self, *args, **kargs):
        gtk.Image.__init__(self, *args, **kargs)
        BaseWidget.__init__(self)


class RichTextImage (RichTextChild):
    """An Image child widget in a RichTextView"""

    def __init__(self):
        RichTextChild.__init__(self)
        self.filename = None
        self._widget = BaseImage()
        self._widget.set_owner(self)
        self._widget.connect("destroy", self.on_image_destroy)
        self.pixbuf = None
    
    def set_filename(self, filename):
        self.filename = filename
    
    def get_filename(self):
        return self.filename
    
    def set_from_file(self, filename):
        if self.filename is None:
            self.filename = os.path.basename(filename)
        
        try:
            self.pixbuf = gdk.pixbuf_new_from_file(filename)            
            
        except gobject.GError, e:            
            self._widget.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
            self.pixbuf = None
            #raise RichTextError("Cannot load image '%s'" % filename, e)
        else:
            self._widget.set_from_pixbuf(self.pixbuf)
        
        #self.pixbuf = self._widget.get_pixbuf()
    
    
    def set_from_pixbuf(self, pixbuf, filename=None):
        if filename is not None:
            self.filename = filename
        self._widget.set_from_pixbuf(pixbuf)
        self.pixbuf = pixbuf
    
    def refresh(self):
        if self._widget is None:
            self._widget = BaseImage()
            self._widget.set_owner(self)
            if self.pixbuf:
                self._widget.set_from_pixbuf(self.pixbuf)
            else:
                self._widget.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
            self._widget.show()
            self._widget.connect("destroy", self.on_image_destroy)
        return self._widget
        
    def copy(self):
        img = RichTextImage()
        img.filename = self.filename
        if self.pixbuf:
            img.get_widget().set_from_pixbuf(self.pixbuf)
        else:
            img.get_widget().set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
        img.pixbuf = self.pixbuf
        img.get_widget().show()
        return img
    
    def on_image_destroy(self, widget):
        self._widget = None
        

#=============================================================================
# RichText classes

class RichTextError (StandardError):
    pass


class RichTextBuffer (gtk.TextBuffer):
    def __init__(self, textview=None):
        gtk.TextBuffer.__init__(self)
        self.clipboard_contents = None
        self.textview = textview
        self._modified = False
        self.undo_stack = UndoStack()
        
        # callbacks
        self.on_modified = None
        
        # action state
        self.insert_mark = None
        self.next_action = None
        self.current_tags = []
        self.anchors = {}
        self.anchors_deferred = {} 
        
        # setup signals
        self.signals = []
        self.signals.append(self.connect("begin_user_action", 
                                         self.on_begin_user_action))
        self.signals.append(self.connect("end_user_action", 
                                         self.on_end_user_action))
        self.signals.append(self.connect("mark-set", 
                                         self.on_mark_set))
        self.signals.append(self.connect("insert-text", 
                                         self.on_insert_text))
        self.signals.append(self.connect("delete-range", 
                                         self.on_delete_range))
        self.signals.append(self.connect("insert-pixbuf", 
                                         self.on_insert_pixbuf))
        self.signals.append(self.connect("insert-child-anchor", 
                                         self.on_insert_child_anchor))
        self.signals.append(self.connect("apply-tag", 
                                         self.on_apply_tag))
        self.signals.append(self.connect("remove-tag", 
                                         self.on_remove_tag))
        self.signals.append(self.connect("changed", 
                                         self.on_changed))
             
        
        
        # font tags        
        self.bold_tag = self.create_tag("Bold", weight=pango.WEIGHT_BOLD)
        self.italic_tag = self.create_tag("Italic", style=pango.STYLE_ITALIC)
        self.underline_tag = self.create_tag("Underline", underline=pango.UNDERLINE_SINGLE)
        
        self.left_tag = self.create_tag("Left", justification=gtk.JUSTIFY_LEFT)
        self.center_tag = self.create_tag("Center", justification=gtk.JUSTIFY_CENTER)
        self.right_tag = self.create_tag("Right", justification=gtk.JUSTIFY_RIGHT)
        self.fill_tag = self.create_tag("Fill", justification=gtk.JUSTIFY_FILL)
        
        self.justify2name = {
            gtk.JUSTIFY_LEFT: "left", 
            gtk.JUSTIFY_RIGHT: "right", 
            gtk.JUSTIFY_CENTER: "center", 
            gtk.JUSTIFY_FILL: "fill" # TODO: implement fully
        }
        
        self.justify_tags = set([self.left_tag, self.center_tag, self.right_tag,
                                 self.fill_tag])
        self.family_tags = set()
        self.size_tags = set()
        
    
    def modify(self):
        tmp = self._modified
        self._modified = True
        if not tmp and self.on_modified:
            self.on_modified(True)

    
    def unmodify(self):
        self._modified = False
        if self.on_modified:
            self.on_modified(False)

        
    
    def is_modified(self):
        return self._modified
        
    
    def set_textview(self, textview):
        self.textview = textview
    
    def get_textview(self):
        return self.textview
    
    def block_signals(self):
        for signal in self.signals:
            self.handler_block(signal)
    
    
    def unblock_signals(self):
        for signal in self.signals:
            self.handler_unblock(signal)
    
    #======================================================
    # copy and paste

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
        
        targets = clipboard.wait_for_targets()
        
        if MIME_TAKENOTE in targets:
            clipboard.request_contents(MIME_TAKENOTE, self.do_paste)
        elif "image/png" in targets:
            clipboard.request_contents("image/png", self.do_paste_image)        
        elif "image/bmp" in targets:
            clipboard.request_contents("image/bmp", self.do_paste_image)        
        elif "image/jpeg" in targets:
            clipboard.request_contents("image/jpeg", self.do_paste_image)
        elif "image/xpm" in targets:
            clipboard.request_contents("image/xpm", self.do_paste_image)
        else:
            clipboard.request_text(self.do_paste_text)
        
    
    def do_paste_text(self, clipboard, text, data):
        self.begin_user_action()
        self.delete_selection(False, True)
        self.insert_at_cursor(text)
        self.end_user_action()
    
    def do_paste_image(self, clipboard, selection_data, data):
        
        pixbuf = selection_data.get_pixbuf()
        image = RichTextImage()
        image.set_from_pixbuf(pixbuf)
        
        self.insert_image(image)
    
    def do_paste(self, clipboard, selection_data, data):
        assert self.clipboard_contents != None
        
        self.begin_user_action()
        it = self.get_iter_at_mark(self.get_insert())
        insert_buffer_contents(self, it, self.clipboard_contents)
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
    
    
    #============================================================
    # actions
    
    def add_child_at_anchor(self, child, anchor):
        self.anchors.setdefault(anchor, []).append(child)
        if self.textview:
            self.textview.add_child_at_anchor(child.get_widget(), anchor)
        else:
            self.anchors_deferred.setdefault(anchor, []).append(child)
    
    
    def add_deferred_anchors(self):
        assert self.textview is not None
        
        for anchor, children in self.anchors_deferred.iteritems():
            # only add anchor if it is still present (hasn't been deleted)
            if anchor in self.anchors:
                for child in children:
                    self.textview.add_child_at_anchor(child.get_widget(), anchor)
        
        self.anchors_deferred.clear()
    
    
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer"""
                
        self.begin_user_action()
        
        it = self.get_iter_at_mark(self.get_insert())
        anchor = self.create_child_anchor(it)
        self.add_child_at_anchor(image, anchor)
        image.get_widget().show()
        
        self.end_user_action()
        
        if image.get_filename() == None:
            filename, ext = os.path.splitext(filename)
            filenames = self.get_image_filenames()
            filename = takenote.get_unique_filename_list(filenames, filename, ext)
            image.set_filename(filename)
    
    
    def get_image_filenames(self):
        filenames = []
        
        # TODO: could be faster (specialized search_forward)
        for kind, it, param in iter_buffer_contents(self):
            if kind == "anchor":
                anchor, widgets = param
                
                for widget in widgets:
                    child = widget.get_owner()
                    
                    if isinstance(child, RichTextImage):
                        filenames.append(child.get_filename())
        
        return filenames    
    
    #===========================================================
    # Callbacks
    
    def on_mark_set(self, textbuffer, it, mark):
        """Callback for mark movement"""
        
        if mark.get_name() == "insert":
            # pick up the last tags
            self.current_tags = it.get_toggled_tags(False)
            
            # update UI for current fonts
            if self.textview:
                self.textview.on_update_font()
            
    
    
    def on_insert_text(self, textbuffer, it, text, length):
        """Callback for text insert"""
        
        # start new action
        self.next_action = InsertAction(self, it.get_offset(), text, length)
        self.insert_mark = self.create_mark(None, it, True)

    def on_delete_range(self, textbuffer, start, end):
        """Callback for delete range"""
    
        # start next action
        self.next_action = DeleteAction(self, start.get_offset(), 
                                        end.get_offset(),
                                        start.get_slice(end),
                                        self.get_iter_at_mark(
                                            self.get_insert()).get_offset())
        
    
    def on_insert_pixbuf(self, textbuffer, it, pixbuf):
        """Callback for inserting a pixbuf"""
        pass
    
    
    def on_insert_child_anchor(self, textbuffer, it, anchor):
        """Callback for inserting a child anchor"""
        self.next_action = InsertChildAction(self, it.get_offset(), anchor)
    
    def on_apply_tag(self, textbuffer, tag, start, end):
        """Callback for tag apply"""
        
        self.begin_user_action()
        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), True)
        self.undo_stack.do(action.do, action.undo, False)
        action = ModifyAction(self)
        self.undo_stack.do(action.do, action.undo)
        self.end_user_action()
    
    def on_remove_tag(self, textbuffer, tag, start, end):
        """Callback for tag remove"""
    
        self.begin_user_action()
        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), False)
        self.undo_stack.do(action.do, action.undo, False)
        action = ModifyAction(self)
        self.undo_stack.do(action.do, action.undo)
        self.end_user_action()
    
    
    def on_changed(self, textbuffer):
        """Callback for buffer change"""
    
        
        if isinstance(self.next_action, InsertAction):
            # apply current style to inserted text
            
            if len(self.current_tags) > 0:
                it = self.get_iter_at_mark(self.insert_mark)
                it2 = it.copy()
                it2.forward_chars(self.next_action.length)

                for tag in self.current_tags:
                    self.apply_tag(tag, it, it2)

                self.delete_mark(self.insert_mark)
                self.insert_mark = None
                
        elif isinstance(self.next_action, DeleteAction):
            # deregister any deleted anchors
            
            for kind, offset, param in self.next_action.contents:
                if kind == "anchor":
                    del self.anchors[param[0]]
        
        
        if self.next_action:
            self.begin_user_action()        
            self.undo_stack.do(self.next_action.do, self.next_action.undo, False)
            self.next_action = None
            action = ModifyAction(self)
            self.undo_stack.do(action.do, action.undo)
            
            self.end_user_action()
    
    #==============================================================
    # Tag manipulation    

    def toggle_tag_selected(self, tag):
        self.begin_user_action()
        it = self.get_selection_bounds()
        
        if len(it) == 0:
            if tag not in self.current_tags:
                self.clear_current_font_tags(tag)
                self.current_tags.append(tag)
            else:
                self.current_tags.remove(tag)
        else:
            self.current_tags = []
            if not it[0].has_tag(tag):
                self.clear_font_tags(tag, it[0], it[1])
                self.apply_tag(tag, it[0], it[1])
            else:
                self.remove_tag(tag, it[0], it[1])
        
        self.end_user_action()
    

    def apply_tag_selected(self, tag):
        self.begin_user_action()    
        it = self.get_selection_bounds()
        
        if len(it) == 0:
            if tag not in self.current_tags:
                self.clear_current_font_tags(tag)
                self.current_tags.append(tag)
        else:
            self.current_tags = []
            self.clear_font_tags(tag, it[0], it[1])
            self.apply_tag(tag, it[0], it[1])
        self.end_user_action()


    def remove_tag_selected(self, tag):
        self.begin_user_action()
        it = self.get_selection_bounds()
        
        if len(it) == 0:
            if tag in self.current_tags:
                self.current_tags.remove(tag)
        else:
            self.current_tags = []
            self.remove_tag(tag, it[0], it[1])
        self.end_user_action()
    
    
    def clear_font_tags(self, tag, start, end):
        
        # remove other justify tags
        if tag in self.justify_tags:
            for tag2 in self.justify_tags:
                self.remove_tag(tag2, start, end)
        
        # remove other family tags        
        elif tag in self.family_tags:
            for tag2 in self.family_tags:
                self.remove_tag(tag2, start, end)
        
        # remove other size tags                    
        elif tag in self.size_tags:
            for tag2 in self.size_tags:
                self.remove_tag(tag2, start, end)

    def clear_current_font_tags(self, tag):
        
        # remove other justify tags
        if tag in self.justify_tags:
            for tag2 in self.justify_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)
        
        # remove other family tags        
        elif tag in self.family_tags:
            for tag2 in self.family_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)
        
        # remove other size tags                    
        elif tag in self.size_tags:
            for tag2 in self.size_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)

    
    #===========================================================
    # Font management
    
    def lookup_family_tag(self, family):
        tag = self.tag_table.lookup(family)
        if tag == None:
            tag = self.create_tag(family, family=family)
            self.add_family_tag(tag)
        return tag
    
    def lookup_size_tag(self, size):
        sizename = "size %d" % size
        tag = self.tag_table.lookup(sizename)
        if tag == None:
            tag = self.create_tag(sizename, size_points=size)
            self.add_size_tag(tag)
        return tag
    
    def add_family_tag(self, tag):
        self.family_tags.add(tag)        
    
    def add_size_tag(self, tag):
        self.size_tags.add(tag)
    

    def parse_font(self, fontstr):
        tokens = fontstr.split(" ")
        size = int(tokens.pop())
        mods = []
        
        # NOTE: underline is not part of the font string and is handled separately
        while tokens[-1] in ["Bold", "Italic"]:
            mods.append(tokens.pop())

        return " ".join(tokens), mods, size
    
    def get_font(self):
        # get iter for retrieving font
        it2 = self.get_selection_bounds()
        
        if len(it2) == 0:
            it = self.get_iter_at_mark(self.get_insert())
        else:
            it = it2[0]
            it.forward_char()
        
        # create a set that is fast for quering the existance of tags
        current_tags = set(self.current_tags)        
        
        # get the text attributes and font at the iter
        if self.textview:
            attr = self.textview.get_default_attributes()
        else:
            attr = gtk.TextAttributes()
        it.get_attributes(attr)        
        font = attr.font
        
        # set family
        family = font.get_family()
        
        # set modifications (current tags override)
        mods = {"bold":
                self.bold_tag in current_tags or
                font.get_weight() == pango.WEIGHT_BOLD,
                "italic": 
                self.italic_tag in current_tags or
                font.get_style() == pango.STYLE_ITALIC,
                "underline":
                self.underline_tag in current_tags or
                attr.underline != pango.UNDERLINE_NONE}      
        
        # set justification
        justify = self.justify2name[attr.justification]
        
        # current tags override
        if self.center_tag in current_tags:
            justify = "center"
            
        elif self.right_tag in current_tags:
            justify = "right"
        
        elif self.fill_tag in current_tags:
            justify = "fill"
        
        # get size in points (get_size() returns pango units)
        size = font.get_size() // 1024
        
        for tag in self.current_tags:
            if tag in self.family_tags:
                family = tag.get_property("name")
            
            elif tag in self.size_tags:
                size = int(tag.get_property("size-points"))
        
        return mods, justify, family, size


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



    

class RichTextView (gtk.TextView):

    def __init__(self):
        gtk.TextView.__init__(self, RichTextBuffer(self))
        self.textbuffer = self.get_buffer()
        self.blank_buffer = gtk.TextBuffer()
        
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.set_property("right-margin", 5)
        self.set_property("left-margin", 5)
        
        self.font_callback = None
        
        self.ignore_font_upate = False
        self.first_menu = True

        # drag and drop
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("drag-motion", self.on_drag_motion)
        self.drag_dest_add_image_targets()

        # clipboard
        self.connect("copy-clipboard", lambda w: self.on_copy())
        self.connect("cut-clipboard", lambda w: self.on_cut())
        self.connect("paste-clipboard", lambda w: self.on_paste())
        
        #[('GTK_TEXT_BUFFER_CONTENTS', 1, 0), ('UTF8_STRING', 0, 0), ('COMPOUND_TEXT', 0, 0), ('TEXT', 0, 0), ('STRING', 0, 0), ('text/plain;charset=utf-8', 0, 0), ('text/plain;charset=ANSI_X3.4-1968', 0, 0), ('text/plain', 0, 0)]
        
        #self.connect("populate-popup", self.on_popup)
        
        # initialize HTML buffer
        self.html_buffer = HtmlBuffer()
        self.html_buffer.add_tag(self.textbuffer.bold_tag, "b")
        self.html_buffer.add_tag(self.textbuffer.italic_tag, "i")
        self.html_buffer.add_tag(self.textbuffer.underline_tag, "u")
        
        # requires new pygtk
        #self.textbuffer.register_serialize_format(MIME_TAKENOTE, 
        #                                          self.serialize, None)
        #self.textbuffer.register_deserialize_format(MIME_TAKENOTE, 
        #                                            self.deserialize, None)


    def set_on_modified(self, func):
        assert self.textbuffer
        
        self.textbuffer.on_modified = func

    def set_buffer(self, textbuffer):
        # tell current buffer we are detached
        if self.textbuffer:
            self.textbuffer.set_textview(None)
        
        # change buffer
        if textbuffer:
            gtk.TextView.set_buffer(self, textbuffer)
        else:
            gtk.TextView.set_buffer(self, self.blank_buffer)
        self.textbuffer = textbuffer
        
        # tell new buffer we are attached
        if self.textbuffer:
            self.textbuffer.set_textview(self)

        

    #=======================================================
    # Drag and drop

    def on_drag_motion(self, textview, drag_context, x, y, timestamp):
        
        # check for image targets
        img_target = self.drag_dest_find_target(drag_context, 
            [("image/png", 0, 0) ,
             ("image/bmp", 0, 0) ,
             ("image/jpeg", 0, 0),
             ("image/xpm", 0, 0)])
             
        if img_target is not None and img_target != "NONE":
            textview.drag_dest_set_target_list([(img_target, 0, 0)])
        
        elif "application/pdf" in drag_context.targets:
            textview.drag_dest_set_target_list([("application/pdf", 0, 0)])
        
        else:
            textview.drag_dest_set_target_list([("text/plain", 0, 0)])
            
    
    
    def on_drag_data_received(self, widget, drag_context, x, y,
                              selection_data, info, eventtime):
        
        img_target = self.drag_dest_find_target(drag_context, 
            [("image/png", 0, 0) ,
             ("image/bmp", 0, 0) ,
             ("image/jpeg", 0, 0),
             ("image/xpm", 0, 0)])
             
        if img_target not in (None, "NONE"):
            pixbuf = selection_data.get_pixbuf()
            
            if pixbuf != None:
                image = RichTextImage()
                image.set_from_pixbuf(pixbuf)
        
                self.insert_image(image)
            
                drag_context.finish(True, True, eventtime)
                self.stop_emission("drag-data-received")
                
                
        elif self.drag_dest_find_target(drag_context, 
                   [("application/pdf", 0, 0)]) not in (None, "NONE"):
            
            
            data = selection_data.data
            
            f, imgfile = tempfile.mkstemp(".png", "takenote")
            os.close(f)
            
            out = os.popen("convert - %s" % imgfile, "wb")
            out.write(data)
            out.close()
            
            name, ext = os.path.splitext(imgfile)
            imgfile2 = name + "-0" + ext
            
            if os.path.exists(imgfile2):
                i = 0
                while True:
                    imgfile = name + "-" + str(i) + ext
                    if not os.path.exists(imgfile):
                        break
                    self.insert_pdf_image(imgfile)
                    os.remove(imgfile)
                    i += 1
                    
            elif os.path.exists(imgfile):
                
                self.insert_pdf_image(imgfile)
                os.remove(imgfile)
            
            drag_context.finish(True, True, eventtime)
            self.stop_emission("drag-data-received")
        
        elif self.drag_dest_find_target(drag_context, 
                   [("text/plain", 0, 0)]) not in (None, "NONE"):
            
            self.insert_at_cursor(selection_data.get_text())
                        
            
    def insert_pdf_image(self, imgfile):
        pixbuf = gdk.pixbuf_new_from_file(imgfile)
        img = RichTextImage()
        img.set_from_pixbuf(pixbuf)
        self.insert_image(img, "pdf.png")

        
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
            
           

    

    
    
    #==================================================================
    # Copy and Paste

    def on_copy(self):
        """Callback for copy action"""
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        self.textbuffer.copy_clipboard(clipboard)
        self.stop_emission('copy-clipboard')
    
    def on_cut(self):
        """Callback for cut action"""    
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        self.textbuffer.cut_clipboard(clipboard, self.get_editable())
        self.stop_emission('cut-clipboard')
    
    def on_paste(self):
        """Callback for paste action"""    
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        self.textbuffer.paste_clipboard(clipboard, None, self.get_editable())
        self.stop_emission('paste-clipboard')

    
    #==================================================================
    # File I/O
    
    def save(self, filename):
        path = os.path.dirname(filename)
        self.save_images(path)
        
        try:
            out = open(filename, "w")
            self.html_buffer.set_output(out)
            self.html_buffer.write(self)
            out.close()
        except IOError, e:
            raise RichTextError("Could not save '%s'" % filename)
        
        self.textbuffer.unmodify()
    
    
    def load(self, filename):
        textbuffer = self.textbuffer
        
        textbuffer.undo_stack.suppress()
        textbuffer.block_signals()
        self.set_buffer(None)
        textbuffer.anchors.clear()
        
        start = textbuffer.get_start_iter()
        end = textbuffer.get_end_iter()
        textbuffer.remove_all_tags(start, end)
        textbuffer.delete(start, end)
        
        try:
            self.html_buffer.read(textbuffer, open(filename, "r"))
        except HtmlError, e:
            print e
            
            # TODO: turn into function
            textbuffer.anchors.clear()
            textbuffer.deferred_anchors.clear()
            self.set_buffer(textbuffer)
            
            ret = False
        else:    
            self.set_buffer(textbuffer)        
            textbuffer.add_deferred_anchors()
        
            path = os.path.dirname(filename)
            self.load_images(path)
            
            ret = True
        
        textbuffer.unblock_signals()
        self.textbuffer.undo_stack.resume()
        self.textbuffer.undo_stack.reset()
        self.enable()
        
        self.textbuffer.unmodify()
        
        if not ret:
            raise RichTextError("error loading '%s'" % filename)
        
    
    
    def enable(self):
        self.set_sensitive(True)
    
    
    def disable(self):
        
        self.textbuffer.undo_stack.suppress()
        
        start = self.textbuffer.get_start_iter()
        end = self.textbuffer.get_end_iter()
        self.textbuffer.remove_all_tags(start, end)
        self.textbuffer.delete(start, end)
        self.set_sensitive(False)
        
        self.textbuffer.undo_stack.resume()
        self.textbuffer.undo_stack.reset()
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
                        child.get_widget().show()

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
    
    
    """
    def serialize(self, register_buf, content_buf, start, end, data):
        print "serialize", content_buf
        self.a = u"SERIALIZED"
        return self.a 
    
    
    def deserialize(self, register_buf, content_buf, it, data, create_tags, udata):
        print "deserialize"
    """
    
    #===========================================================
    # Actions
        
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer"""
                
        self.textbuffer.insert_image(image, filename)    
    
    
    def forward_search(self, it, text, case_sensitive):
        it = it.copy()
        text = unicode(text, "utf8")
        if not case_sensitive:
            text = text.lower()
        
        textlen = len(text)
        
        while True:
            end = it.copy()
            end.forward_chars(textlen)
                        
            text2 = it.get_slice(end)
            if not case_sensitive:
                text2 = text2.lower()
            
            if text2 == text:
                return it, end
            if not it.forward_char():
                return None
    
    
    def backward_search(self, it, text, case_sensitive):
        it = it.copy()
        it.backward_char()
        text = unicode(text, "utf8")
        if not case_sensitive:
            text = text.lower()
        
        textlen = len(text)
        
        while True:
            end = it.copy()
            end.forward_chars(textlen)
                        
            text2 = it.get_slice(end)
            if not case_sensitive:
                text2 = text2.lower()
            
            if text2 == text:
                return it, end
            if not it.backward_char():
                return None

        
    
    def find(self, text, case_sensitive=False, forward=True, next=True):
        # TODO: non-case_sensitive is ignored
        
        if not self.textbuffer:
            return
        
        it = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
        
        
        if forward:
            if next:
                it.forward_char()
            result = self.forward_search(it, text, case_sensitive)
        else:
            result = self.backward_search(it, text, case_sensitive)
        
        if result:
            self.textbuffer.select_range(result[0], result[1])
            self.scroll_mark_onscreen(self.textbuffer.get_insert())
            return result[0].get_offset()
        else:
            return -1
        
        
    def replace(self, text, replace_text, 
                case_sensitive=False, forward=True, next=True):
        
        pos = self.find(text, case_sensitive, forward, next)
        
        if pos != -1:
            self.textbuffer.begin_user_action()
            self.textbuffer.delete_selection(True, self.get_editable())
            self.textbuffer.insert_at_cursor(replace_text)
            self.textbuffer.end_user_action()
            
        return pos
        
            
    def replace_all(self, text, replace_text, 
                    case_sensitive=False, forward=True):
        found = False
        
        self.textbuffer.begin_user_action()
        while self.replace(text, replace_text, case_sensitive, forward, False) != -1:
            found = True
        self.textbuffer.end_user_action()
        
        return found
        
        
    #===========================================================
    # Callbacks from UI to change font 

    def on_bold(self):
        self.textbuffer.toggle_tag_selected(self.textbuffer.bold_tag)
        
    def on_italic(self):
        self.textbuffer.toggle_tag_selected(self.textbuffer.italic_tag)
    
    def on_underline(self):
        self.textbuffer.toggle_tag_selected(self.textbuffer.underline_tag)       
    
    def on_font_set(self, widget):
        family, mods, size = self.textbuffer.parse_font(widget.get_font_name())
        
        # apply family tag
        self.textbuffer.apply_tag_selected(self.textbuffer.lookup_family_tag(family))
        
        # apply size
        self.textbuffer.apply_tag_selected(self.textbuffer.lookup_size_tag(size))
        
        # apply mods
        for mod in mods:
            self.textbuffer.apply_tag_selected(self.textbuffer.tag_table.lookup(mod))
        
        # disable mods not given
        for mod in ["Bold", "Italic", "Underline"]:
            if mod not in mods:
                self.textbuffer.remove_tag_selected(self.textbuffer.tag_table.lookup(mod))
    
    def on_font_family_set(self, family):
        self.textbuffer.apply_tag_selected(self.textbuffer.lookup_family_tag(family))
    
    def on_font_family_toggle(self, family):
        self.textbuffer.toggle_tag_selected(self.textbuffer.lookup_family_tag(family))
    
    def on_font_size_set(self, size):
        self.textbuffer.apply_tag_selected(self.textbuffer.lookup_size_tag(size))
    
    def on_left_justify(self):
        self.textbuffer.apply_tag_selected(self.textbuffer.left_tag)
        
    def on_center_justify(self):
        self.textbuffer.apply_tag_selected(self.textbuffer.center_tag)
    
    def on_right_justify(self):
        self.textbuffer.apply_tag_selected(self.textbuffer.right_tag)
    
    def on_fill_justify(self):
        self.textbuffer.apply_tag_selected(self.textbuffer.fill_tag)
    
    #==================================================================
    # UI Updating from chaning font under cursor
    
    def on_update_font(self):
        mods, justify, family, size = self.get_font()
        
        if self.font_callback:
            self.font_callback(mods, justify, family, size)
    
    def get_font(self):
        return self.textbuffer.get_font()
    
    
    #=========================================
    # undo/redo methods
    
    def undo(self):
        """Undo the last action in the RichTextView"""
        self.textbuffer.undo()
        
    def redo(self):
        """Redo the last action in the RichTextView"""    
        self.textbuffer.redo()    





