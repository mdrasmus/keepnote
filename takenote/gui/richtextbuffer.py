
# python imports
import sys, os, tempfile, re
import urllib2


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
     add_child_to_buffer



# TODO: fix bug with spell check interferring with underline tags

# these tags will not be enumerated by iter_buffer_contents
IGNORE_TAGS = set(["gtkspell-misspelled"])

# default maximum undo levels
MAX_UNDOS = 100

# string for bullet points
BULLET_STR = u"\u2022 "




class RichTextError (StandardError):
    """Class for errors with RichText"""

    # NOTE: this is only used for saving and loading in textview
    # should this stay here?
    
    def __init__(self, msg, error):
        StandardError.__init__(self, msg)
        self.msg = msg
        self.error = error
    
    def __str__(self):
        if self.error:
            return str(self.error) + "\n" + self.msg
        else:
            return self.msg



#=============================================================================
# RichText child objects


class RichTextAnchor (gtk.TextChildAnchor):
    """Base class of all anchor objects in a RichTextView"""
    
    def __init__(self):
        gtk.TextChildAnchor.__init__(self)
        self._widget = None
        self._buffer = None
    
    def get_widget(self):
        return self._widget

    def set_buffer(self, buf):
        self._buffer = buf
    
    def copy(slef):
        anchor = RichTextAnchor()
        anchor.set_buffer(self._buffer)
        return anchor
    
    def highlight(self):
        if self._widget:
            self._widget.highlight()
    
    def unhighlight(self):
        if self._widget:
            self._widget.unhighlight()

gobject.type_register(RichTextAnchor)
gobject.signal_new("selected", RichTextAnchor, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, ())
gobject.signal_new("activated", RichTextAnchor, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, ())
gobject.signal_new("popup-menu", RichTextAnchor, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (int, object))


class BaseWidget (object):
    """Widgets in RichTextBuffer must support this interface"""
    
    def __init__(self):
        pass
        
    def highlight(self):
        pass
    
    def unhighlight(self):
        pass


class RichTextSep (gtk.HSeparator, BaseWidget):
    """Separator widget for a Horizontal Rule"""
    def __init__(self):
        gtk.HSeparator.__init__(self)
        BaseWidget.__init__(self)
        self.modify_bg(gtk.STATE_NORMAL, gdk.Color(0, 0, 0))
        self.modify_fg(gtk.STATE_NORMAL, gdk.Color(0, 0, 0))
        self.connect("size-request", self.on_resize)

    def on_resize(self, sep, req):
        req.height = 10
        req.width = self.get_parent().get_allocation().width - 20
        
    

class RichTextHorizontalRule (RichTextAnchor):
    def __init__(self):
        gtk.TextChildAnchor.__init__(self)
        self._widget = RichTextSep()
        #width = 400
        #height = 1
        #color = 0 # black
        #padding = 5

        #pixbuf = gdk.Pixbuf(gdk.COLORSPACE_RGB, False, 8, width, height)
        #pixbuf.fill(color)
        #self._widget.set_from_pixbuf(pixbuf)
        #self._widget.img.set_padding(0, padding)
        self._widget.show()
    
    def get_widget(self):
        return self._widget
    
    def copy(slef):
        return RichTextHorizontalRule()
       

class BaseImage (gtk.EventBox, BaseWidget):
    """Subclasses gtk.Image to make an Image Widget that can be used within
       RichTextViewS"""

    def __init__(self, *args, **kargs):
        gtk.EventBox.__init__(self)
        BaseWidget.__init__(self)
        self._img = gtk.Image(*args, **kargs)
        self.add(self._img)

        # TODO: will this be configurable?
        # set to white background
        self.modify_bg(gtk.STATE_NORMAL, gdk.Color(65535, 65535, 65535))

        # gtk.STATE_ACTIVE
        # gtk.STATE_PRELIGHT
        # gtk.STATE_SELECTED
        # gtk.STATE_INSENSITIVE

    
    def highlight(self):
        self.drag_highlight()
    
    def unhighlight(self):
        self.drag_unhighlight()
    
    def set_from_pixbuf(self, pixbuf):
        self._img.set_from_pixbuf(pixbuf)
    
    def set_from_stock(self, stock, size):
        self._img.set_from_stock(stock, size)
    
    def show(self):
        gtk.EventBox.show(self)
        self._img.show()


# TODO: think about how a single anchor could manage multiple widgets in
# multiple textviews

class RichTextImage (RichTextAnchor):
    """An Image child widget in a RichTextView"""

    def __init__(self):
        RichTextAnchor.__init__(self)
        self._filename = None
        self._download = False
        self._widget = BaseImage()
        self._widget.connect("destroy", self._on_image_destroy)
        self._widget.connect("button-press-event", self._on_clicked)
        self._pixbuf = None
        self._pixbuf_original = None
        self._size = [None, None]
        self._buffer = None
        self._save_needed = False
        

    def is_valid(self):
        """Did the image successfully load an image"""
        return self._pixbuf is not None
    
    def set_filename(self, filename):
        """Sets the filename used for saving image"""
        self._filename = filename
    
    def get_filename(self):
        """Returns the filename used for saving image"""
        return self._filename

    def set_save_needed(self, save):
        """Sets whether image needs to be saved to disk"""
        self._save_needed = save

    def save_needed(self):
        """Returns True if image needs to be saved to disk"""
        return self._save_needed
    
    def set_from_file(self, filename):
        """Sets the image from a file"""
        
        if self._filename is None:
            self._filename = os.path.basename(filename)
        
        try:
            self._pixbuf_original = gdk.pixbuf_new_from_file(filename)
            
        except gobject.GError, e:
            # use missing image instead
            self._widget.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
            self._pixbuf_original = None
            self._pixbuf = None
        else:
            # successful image load, set its size
            self._pixbuf = self._pixbuf_original
            
            if self.is_size_set():
                self.scale(self._size[0], self._size[1], False)
            self._widget.set_from_pixbuf(self._pixbuf)


    def set_from_pixbuf(self, pixbuf, filename=None):
        """Set the image from a pixbuf"""
        
        if filename is not None:
            self._filename = filename
        self._pixbuf = pixbuf
        self._pixbuf_original = pixbuf

        if self.is_size_set():
            self.scale(self._size[0], self._size[1], False)
        self._widget.set_from_pixbuf(self._pixbuf)


    def get_original_pixbuf(self):
        """Returns the pixbuf of the image at its original size (no scaling)"""
        return self._pixbuf_original

                
    def get_size(self, actual_size=False):
        """Returns the size of the image

           actual_size -- if True, None values will be replaced by original size
        """
        
        if actual_size:
            if self._pixbuf_original is not None:
                w, h = self._size
                if w is None:
                    w = self._pixbuf_original.get_width()
                if h is None:
                    h = self._pixbuf_original.get_height()
                return [w, h]
            else:
                return [0, 0]
        else:
            return self._size

    def get_original_size(self):
        return [self._pixbuf_original.get_width(),
                self._pixbuf_original.get_height()]


    def is_size_set(self):
        return self._size[0] is not None or self._size[1] is not None
    

    def scale(self, width, height, set_widget=True):
        """Scale the image to a new width and height"""

        if not self.is_valid:
            return
        
        self._size = [width, height]

        
        if not self.is_size_set():
            # use original image size
            if self._pixbuf != self._pixbuf_original:
                self._pixbuf = self._pixbuf_original
                if self._pixbuf is not None:
                    self._widget.set_from_pixbuf(self._pixbuf)
        
        elif self._pixbuf_original is not None:
            # perform scaling
            
            width2 = self._pixbuf_original.get_width()
            height2 = self._pixbuf_original.get_height()
            
            if width is None:
                factor = height / float(height2)
                width = factor * width2
            if height is None:
                factor = width / float(width2)
                height = factor * height2
            
            self._pixbuf = self._pixbuf_original.scale_simple(
                width, height, gtk.gdk.INTERP_BILINEAR)

            if set_widget:
                self._widget.set_from_pixbuf(self._pixbuf)

        if self._buffer is not None:
            self._buffer.set_modified(True)


    
    def write(self, filename):
        """Write image to file"""
        f, ext = os.path.splitext(filename)
        ext = ext.replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
            
        self._pixbuf_original.save(filename, ext)
        self._save_needed = False
        
        
    def copy(self):
        """Returns a new copy of the image"""
        img = RichTextImage()
        img.set_filename(self._filename)
        img._size = self.get_size()
        
        if self._pixbuf:
            img.get_widget().set_from_pixbuf(self._pixbuf)
        else:
            img.get_widget().set_from_stock(gtk.STOCK_MISSING_IMAGE,
                                            gtk.ICON_SIZE_MENU)
        img._pixbuf = self._pixbuf
        img._pixbuf_original = self._pixbuf_original
        img.get_widget().show()
        return img

    def set_from_url(self, url, filename):
        """Set image by url"""
        
        # make local temp file
        f, imgfile = tempfile.mkstemp("", "takenote")
        os.close(f)
        
        # open url and download image
        infile = urllib2.urlopen(url)
        outfile = open(imgfile, "wb")
        outfile.write(infile.read())
        outfile.close()
        
        # set filename and image
        self.set_from_file(imgfile)
        self.set_filename(filename)

        # remove tempfile
        os.remove(imgfile)

        

    #==========================
    # GUI callbacks
    
    def _on_image_destroy(self, widget):
        self._widget = None
    
    def _on_clicked(self, widget, event):
        """Callback for when image is clicked"""
        
        if event.button == 1:
            # left click selects image
            self._widget.grab_focus()
            self.emit("selected")

            if event.type == gtk.gdk._2BUTTON_PRESS:
                # double left click activates image
                self.emit("activated")
            
            return True
        
        elif event.button == 3:
            # right click presents popup menu
            self.emit("selected")
            self.emit("popup-menu", event.button, event.time)
            return True



    

#=============================================================================
# RichTextBuffer


class IndentManager (object):
    """This object will manage the indentation of paragraphs in a
       TextBuffer with RichTextTags
    """

    def __init__(self, textbuffer, apply_exclusive_tag):
        self._buf = textbuffer
        self._apply_exclusive_tag = apply_exclusive_tag

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
            sel = self._buf.get_selection_bounds()

            if not sel:
                start, end = self.get_paragraph()
            else:
                start, _ = self.get_paragraph(sel[0])
                _, end = self.get_paragraph(sel[1])

        self._buf.begin_user_action()

        end_mark = self._buf.create_mark(None, end, True)
        
        # loop through paragraphs
        pos = start
        while pos.compare(end) == -1:
            par_end = pos.copy()
            par_end.forward_line()
            indent, par_indent = self.get_indent(pos)

            if indent + change > 0:
                self._apply_exclusive_tag(
                    self._buf.tag_table.lookup_indent(indent + change,
                                                 par_indent),
                    pos, par_end)
            elif indent > 0:
                # remove indent and possible bullets
                self._buf.remove_tag(self._buf.tag_table.lookup_indent(indent,
                                                             par_indent),
                                pos, par_end)                
                pos = self._remove_bullet(pos)
                end = self._buf.get_iter_at_mark(end_mark)

            if not pos.forward_line():
                break

        self._buf.end_user_action()

        self._buf.delete_mark(end_mark)
        


    def toggle_bullet_list(self):
        """Toggle the state of a bullet list"""
        
        self._buf.begin_user_action()

        # start indent if it is not present
        indent, par_type = self.get_indent()
        if indent == 0:
            indent = 1
            #self.indent()
        
        par_start, par_end = self.get_paragraph()

        if par_type != "none":
            par_type = "none"
        else:
            par_type = "bullet"

        # apply indent to whole paragraph
        indent_tag = self._buf.tag_table.lookup_indent(indent, par_type)
        self._apply_exclusive_tag(indent_tag, par_start, par_end)
            
        self._queue_update_indentation(par_start, par_end)
        
        self._buf.end_user_action()


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
        self._apply_exclusive_tag(bullet_tag, par_start, bullet_end)

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
            self._buf.remove_tag(bullet_tag, par_start, bullet_end)

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

        if self._indent_update:
            self._indent_update = False 

            # perfrom indentation update
            self._buf.begin_user_action()
            #print "start"

            # fixup indentation tags
            # The general rule is that the indentation at the start of
            # each paragraph should determines the indentation of the rest
            # of the paragraph

            pos = self._buf.get_iter_at_mark(self._indent_update_start)
            end = self._buf.get_iter_at_mark(self._indent_update_end)

            end.forward_line()

            # move pos to start of line
            pos = self.move_to_start_of_line(pos)
            assert pos.starts_line(), "pos does not start line before"
            
            while pos.compare(end) == -1:
                assert pos.starts_line(), "pos does not start line"
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
                        pos, par_end = self.get_paragraph(it)
                        break
                    print "match"
                    self._buf.move_mark(self._indent_update_start, match[0])
                    self._buf.delete(match[0], match[1])
                    it = self._buf.get_iter_at_mark(self._indent_update_start)
                    par_end = it.copy()
                    par_end.forward_line()

                if indent_tag is None:
                    # remove all indent tags
                    self._buf.clear_tag_class(self._buf.tag_table.lookup_indent(1),
                                         pos, par_end)
                    # remove bullets
                    par_type = "none"

                else:
                    self._apply_exclusive_tag(indent_tag, pos, par_end)

                    # check for bullets
                    par_type = indent_tag.get_par_indent()
                    
                if par_type == "bullet":
                    pass
                    # ensure proper bullet is in place
                    pos = self._insert_bullet(pos)
                    end = self._buf.get_iter_at_mark(self._indent_update_end)
                    
                elif par_type == "none":
                    pass
                    # remove bullets
                    pos = self._remove_bullet(pos)
                    end = self._buf.get_iter_at_mark(self._indent_update_end)
                    
                else:
                    raise Exception("unknown par_type '%s'" % par_type)
                    

                # move forward a line
                if not pos.forward_line():
                    break

            #print "end"
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
        

    def get_paragraph(self, it=None):
        """Returns the start and end of a paragraph containing iter 'it'"""

        if not it:
            par_start = self._buf.get_iter_at_mark(self._buf.get_insert())
        else:
            par_start = it.copy()
        
        par_end = par_start.copy()
        if par_start.get_line() > 0:
            par_start.backward_line()
            par_start.forward_line()
        else:
            par_start = self._buf.get_start_iter()
        par_end.forward_line()

        # NOTE: par_start.starts_line() == True
        #       par_end.starts_line() == True
        
        return par_start, par_end

    def starts_par(self, it):
        """Returns True if iter 'it' starts paragraph"""

        if it.starts_line():
            return True
        else:
            it2 = it.copy()
            it2 = self.move_to_start_of_line(it2)
            
            return self.par_has_bullet(it2) and \
                   it.get_offset() <= it2.get_offset() + len(BULLET_STR)


    def move_to_start_of_line(self, it=None):
        if not it:
            it = self._buf.get_iter_at_mark(self._buf.get_insert())
        if not it.starts_line():
            if it.get_line() > 0:
                it.backward_line()
                it.forward_line()
            else:
                it = self._buf.get_start_iter()
        return it


#=============================================================================
    
class RichTextBuffer (RichTextBaseBuffer):
    """
    TextBuffer specialized for rich text editing

    It builds upon the features of RichTextBaseBuffer
    - maintains undo/redo stacks
    - manages "current font" behavior

    Additional Features
    - manages specific child widget actions
      - images
      - horizontal rule
    - manages editing of indentation levels and bullet point lists
    
    """
    
    def __init__(self, textview=None):
        RichTextBaseBuffer.__init__(self)
        self.textview = textview


        # indentation manager
        self._indent = IndentManager(self, self.apply_tag_selected)

        # set of all anchors in buffer
        self._anchors = set()

        # anchors that still need to be added,
        # they are defferred because textview was not available at insert-time
        self._anchors_deferred = set() 
        
        

    def set_textview(self, textview):
        self.textview = textview
    
    def get_textview(self):
        return self.textview

    def clear(self):
        """Clear buffer contents"""
        
        RichTextBaseBuffer.clear(self)
        self._anchors.clear()
        self._anchors_deferred.clear()


    def insert_contents(self, contents, it=None):
        """Inserts a content stream into the TextBuffer at iter 'it'"""

        if it is None:
            it = self.get_iter_at_mark(self.get_insert())

        self.begin_user_action()
        insert_buffer_contents(self, it,
                               contents,
                               add_child_to_buffer,
                               lookup_tag=lambda name:
                                   self.tag_table.lookup(name))
        self.end_user_action()


    def copy_contents(self, start, end):
        """Return a content stream for copying from iter start and end"""

        contents = iter(iter_buffer_contents(self, start, end, IGNORE_TAGS))

        # remove regions that can't be copied
        for item in contents:
            if item[0] == "begin" and not item[2].can_be_copied():
                end_tag = item[2]
                
                while not (item[0] == "end" and item[2] == end_tag):
                    item = contents.next()

                    if item[0] not in ("text", "anchor") and \
                       item[2] != end_tag:
                        yield item
                    
                continue

            yield item

    def on_selection_changed(self):
        self.highlight_children()

    def on_ending_user_action(self):
        """
        Callback for when user action is about to end
        Convenient for implementing extra actions that should be included
        in current user action
        """

        # perfrom queued indentation updates
        self._indent.update_indentation()

    #=========================================
    # indentation interface

    def indent(self, start=None, end=None):
        """Indent paragraph level"""
        self._indent.change_indent(start, end, 1)


    def unindent(self, start=None, end=None):
        """Unindent paragraph level"""

        try:
            self._indent.change_indent(start, end, -1)
        except Exception, e:
            print e

    def starts_par(self, it):
        """Returns True if iter 'it' starts a paragraph"""
        return self._indent.starts_par(it)

    def toggle_bullet_list(self):
        """Toggle the state of a bullet list"""
        self._indent.toggle_bullet_list()

    def get_indent(self, it=None):
        return self._indent.get_indent(it)
    
    
    #============================================================
    # child actions
    
    def add_child(self, it, child):

        # preprocess child
        if isinstance(child, RichTextImage):
            self._determine_image_name(child)

        # setup child
        self._anchors.add(child)
        child.set_buffer(self)
        child.connect("activated", self._on_child_activated)
        child.connect("selected", self._on_child_selected)
        child.connect("popup-menu", self._on_child_popup_menu)
        self.insert_child_anchor(it, child)

        # if textview is attaced, let it display child
        if self.textview:
            self.textview.add_child_at_anchor(child.get_widget(), child)
        else:
            # defer display of child
            self._anchors_deferred.add(child)
    
    
    def add_deferred_anchors(self):
        """Add anchors that were deferred"""
        assert self.textview is not None
        
        for child in self._anchors_deferred:
            # only add anchor if it is still present (hasn't been deleted)
            if child in self._anchors:
                self.textview.add_child_at_anchor(child.get_widget(), child)
        
        self._anchors_deferred.clear()
    
    
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer at current position"""

        # set default filename
        if image.get_filename() is None:
            image.set_filename(filename)
        
        # insert image into buffer
        self.begin_user_action()
        it = self.get_iter_at_mark(self.get_insert())
        self.add_child(it, image)
        image.get_widget().show()
        self.end_user_action()


    def insert_hr(self):
        """Insert Horizontal Rule"""
        self.begin_user_action()

        it = self.get_iter_at_mark(self.get_insert())
        hr = RichTextHorizontalRule()
        self.add_child(it, hr)
        
        self.end_user_action()
        

    #===================================
    # Image management

    def get_image_filenames(self):
        filenames = []
        
        for child in self._anchors:
            if isinstance(child, RichTextImage):
                filenames.append(child.get_filename())
        
        return filenames
    

    def _determine_image_name(self, image):
        """Determines image filename"""
        
        if self._is_new_pixbuf(image.get_original_pixbuf()):
            filename, ext = os.path.splitext(image.get_filename())
            filenames = self.get_image_filenames()
            filename2 = takenote.get_unique_filename_list(filenames,
                                                          filename, ext)
            image.set_filename(filename2)
            image.set_save_needed(True)
    

    def _is_new_pixbuf(self, pixbuf):

        # cannot tell if pixbuf is new because it is not loaded
        if pixbuf is None:
            return False
        
        for child in self._anchors:
            if isinstance(child, RichTextImage):
                if pixbuf == child.get_original_pixbuf():
                    return False
        return True
        
    


    #==============================================
    # Child callbacks

    def _on_child_selected(self, child):
        """Callback for when child object is selected

           Make sure buffer knows the selection
        """
        
        it = self.get_iter_at_child_anchor(child)        
        end = it.copy()        
        end.forward_char()
        self.select_range(it, end)


    def _on_child_activated(self, child):
        """Callback for when child is activated (e.g. double-clicked)"""

        # forward callback to listeners (textview)
        self.emit("child-activated", child)
    

    def _on_child_popup_menu(self, child, button, activate_time):
        """Callback for when child's menu is visible"""

        # forward callback to listeners (textview)
        self.emit("child-menu", child, button, activate_time)
            
    
    def highlight_children(self):
        """Highlight any children that are within selection range"""
        
        sel = self.get_selection_bounds()
        focus = None
        
        if len(sel) > 0:
            
            # selection exists, get range (a, b)
            a = sel[0].get_offset()
            b = sel[1].get_offset()
            for child in self._anchors:
                it = self.get_iter_at_child_anchor(child)
                offset = it.get_offset()
                if a <= offset < b:
                    child.highlight()
                else:
                    child.unhighlight()

                w = child.get_widget()
                if w:
                    top = w.get_toplevel()
                    if top:
                        f = top.get_focus()
                        if f:
                            focus = f
            if focus:
                focus.grab_focus()
        else:
            # no selection, unselect all children
            for child in self._anchors:
                child.unhighlight()


    # TODO: need to overload get_font to be indent aware


gobject.type_register(RichTextBuffer)
gobject.signal_new("font-change", RichTextBuffer, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("child-activated", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("child-menu", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object, object, object))
#gobject.signal_new("modified", RichTextView, gobject.SIGNAL_RUN_LAST, 
#    gobject.TYPE_NONE, (bool,))

