
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
     RichTextFont, \
     add_child_to_buffer

from takenote.gui.richtextbuffer_indent import IndentManager

# TODO: fix bug with spell check interferring with underline tags

# these tags will not be enumerated by iter_buffer_contents
IGNORE_TAGS = set(["gtkspell-misspelled"])

# default maximum undo levels
MAX_UNDOS = 100

# string for bullet points
BULLET_STR = u"\u2022 "

# NOTE: use a blank user agent for downloading images
# many websites refuse the python user agent
USER_AGENT = ""



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
            self.set_no_image()
        else:
            # successful image load, set its size
            self._pixbuf = self._pixbuf_original
            
            if self.is_size_set():
                self.scale(self._size[0], self._size[1], False)
            self._widget.set_from_pixbuf(self._pixbuf)


    def set_no_image(self):
        self._widget.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
        self._pixbuf_original = None
        self._pixbuf = None


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

        imgfile = None

        try:
            # make local temp file
            f, imgfile = tempfile.mkstemp("", "takenote")
            os.close(f)
        
            # open url and download image
            opener = urllib2.build_opener()
            request = urllib2.Request(url)
            request.add_header('User-Agent', USER_AGENT)
            infile = opener.open(request)
            
            # infile = urllib2.urlopen(url)
            
            outfile = open(imgfile, "wb")
            outfile.write(infile.read())
            outfile.close()
        
        except Exception: #urllib2.HTTPError, e:
            imgfile = None


        if imgfile:
            # set filename and image
            self.set_from_file(imgfile)
            self.set_filename(filename)
        else:
            self.set_no_image()
            
        # remove tempfile
        if imgfile and os.path.exists(imgfile):
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
# font

class RichTextFontIndent (RichTextFont):
    """Class for representing a font in a simple way"""
    
    def __init__(self):
        self.indent = 0
        self.par_type = "none"

    def set_font(self, attr, tags, current_tags, tag_table):
        # set basic font attr
        RichTextFont.set_font(self, attr, tags, current_tags, tag_table)

        # set indentation info
        for tag in tags:
            if isinstance(tag, RichTextIndentTag):
                self.indent = tag.get_indent()
                self.par_type = tag.get_par_indent()
        
        

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
        self._indent = IndentManager(self)

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
        """Callback for when selection changes"""
        self.highlight_children()

    def on_ending_user_action(self):
        """
        Callback for when user action is about to end
        Convenient for implementing extra actions that should be included
        in current user action
        """

        # perfrom queued indentation updates
        if not self.undo_stack.is_in_progress():
            self._indent.update_indentation()

    def on_paragraph_split(self, start, end):
        """Callback for when paragraphs split"""
        self._indent.on_paragraph_split(start, end)

    def on_paragraph_merge(self, start, end):
        """Callback for when paragraphs merge"""
        self._indent.on_paragraph_merge(start, end)

    def on_paragraph_change(self, start, end):
        """Callback for when paragraph type changes"""
        self._indent.on_paragraph_change(start, end)

    def is_insert_allowed(self, it, text=""):
        """Returns True if insertion is allowed at iter 'it'"""

        # ask the indentation manager whether the insert is allowed
        return self._indent.is_insert_allowed(it, text) and \
               it.can_insert(True)
    

    def _on_delete_range(self, textbuffer, start, end):

        # let indent manager prepare the delete
        #if self.is_interactive():
        #    self._indent.prepare_delete_range(start, end)
                
        # call super class
        RichTextBaseBuffer._on_delete_range(self, textbuffer, start, end)
        
        # deregister any deleted anchors
        for kind, offset, param in self._next_action.contents:
            if kind == "anchor":
                self._anchors.remove(param[0])

    #=========================================
    # indentation interface

    def indent(self, start=None, end=None):
        """Indent paragraph level"""
        self._indent.change_indent(start, end, 1)


    def unindent(self, start=None, end=None):
        """Unindent paragraph level"""
        self._indent.change_indent(start, end, -1)

    def starts_par(self, it):
        """Returns True if iter 'it' starts a paragraph"""
        return self._indent.starts_par(it)

    def toggle_bullet_list(self, par_type=None):
        """Toggle the state of a bullet list"""
        self._indent.toggle_bullet_list(par_type)

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
    def get_font(self, font=None):
        """Get font under cursor"""

        if font is None:
            font = RichTextFontIndent()
        return RichTextBaseBuffer.get_font(self, font)


gobject.type_register(RichTextBuffer)
gobject.signal_new("child-activated", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("child-menu", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object, object, object))
#gobject.signal_new("modified", RichTextView, gobject.SIGNAL_RUN_LAST, 
#    gobject.TYPE_NONE, (bool,))

