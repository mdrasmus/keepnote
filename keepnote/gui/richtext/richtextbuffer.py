"""

    KeepNote
    Richtext buffer class

"""


#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@alum.mit.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#


# python imports
import sys, os, tempfile, re
import urllib2
from itertools import chain

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# TODO: remove
# keepnote imports
import keepnote


# textbuffer imports
from .textbuffer_tools import \
    move_to_start_of_line, \
    move_to_end_of_line, \
    iter_buffer_contents, \
    iter_buffer_anchors, \
    buffer_contents_iter_to_offset, \
    normalize_tags, \
    insert_buffer_contents, \
    buffer_contents_apply_tags

# richtext imports
from .richtextbasebuffer import \
    RichTextBaseBuffer, \
    add_child_to_buffer, \
    RichTextAnchor
from .indent_handler import IndentHandler
from .font_handler import \
    FontHandler, RichTextBaseFont


# richtext tags imports
from .richtext_tags import \
    RichTextTagTable, \
    RichTextTag, \
    RichTextModTag, \
    RichTextJustifyTag, \
    RichTextFamilyTag, \
    RichTextSizeTag, \
    RichTextFGColorTag, \
    RichTextBGColorTag, \
    RichTextIndentTag, \
    RichTextBulletTag, \
    RichTextLinkTag, \
    color_to_string, \
    get_attr_size


# these tags will not be enumerated by iter_buffer_contents
IGNORE_TAGS = set(["gtkspell-misspelled"])

# default maximum undo levels
MAX_UNDOS = 100

# string for bullet points
BULLET_STR = u"\u2022 "

# NOTE: use a blank user agent for downloading images
# many websites refuse the python user agent
USER_AGENT = ""

# default color of a richtext background
DEFAULT_BGCOLOR = (65535, 65535, 65535)

DEFAULT_HR_COLOR = (0, 0, 0)


def ignore_tag(tag):
    return tag.get_property("name") in IGNORE_TAGS


# TODO: Maybe move somewhere more general
def download_file(url, filename):
    """Download a url to a file 'filename'"""
    
    try:
        # open url and download image
        opener = urllib2.build_opener()
        request = urllib2.Request(url)
        request.add_header('User-Agent', USER_AGENT)
        infile = opener.open(request)

        outfile = open(filename, "wb")
        outfile.write(infile.read())
        outfile.close()
        
        return True

    except Exception, e:
        return False
        



#=============================================================================
# RichText child objects

# TODO: remove init signals


class BaseWidget (gtk.EventBox):
    """Widgets in RichTextBuffer must support this interface"""
    
    def __init__(self):
        gtk.EventBox.__init__(self)

        # TODO: will this be configurable?
        # set to white background
        self.modify_bg(gtk.STATE_NORMAL, gdk.Color(*DEFAULT_BGCOLOR))

        # gtk.STATE_ACTIVE
        # gtk.STATE_PRELIGHT
        # gtk.STATE_SELECTED
        # gtk.STATE_INSENSITIVE        
        
    def highlight(self):
        pass
    
    def unhighlight(self):
        pass

    def show(self):
        gtk.EventBox.show_all(self)


#gobject.type_register(BaseWidget)
#gobject.signal_new("init", BaseWidget, gobject.SIGNAL_RUN_LAST, 
#                   gobject.TYPE_NONE, ())


class RichTextSep (BaseWidget):
    """Separator widget for a Horizontal Rule"""

    def __init__(self):
        BaseWidget.__init__(self)
        self._sep = gtk.HSeparator()
        self.add(self._sep)
        self._size = None
        
        self._sep.modify_bg(gtk.STATE_NORMAL, gdk.Color(* DEFAULT_HR_COLOR))
        self._sep.modify_fg(gtk.STATE_NORMAL, gdk.Color(* DEFAULT_HR_COLOR))

        self.connect("size-request", self._on_resize)
        self.connect("parent-set", self._on_parent_set)
        
        self._resizes_id = None

        #pixbuf = gdk.Pixbuf(gdk.COLORSPACE_RGB, False, 8, width, height)
        #pixbuf.fill(color)
        #self._widget.set_from_pixbuf(pixbuf)
        #self._widget.img.set_padding(0, padding)


    def _on_parent_set(self, widget, old_parent):
        """Callback for changing parent"""
        
        if old_parent:
            old_parent.disconnect(self._resize_id)

        if self.get_parent():
            self._resize_id = self.get_parent().connect("size-allocate", 
                                                        self._on_size_change)

    def _on_size_change(self, widget, req):
        """callback for parent's changed size allocation"""

        w, h = self.get_desired_size()
        self.set_size_request(w, h)


    def _on_resize(self, sep, req):
        """Callback for widget resize"""

        w, h = self.get_desired_size()
        req.width = w
        req.height = h


    def get_desired_size(self):
        """Returns the desired size"""

        HR_HORIZONTAL_MARGIN = 20
        HR_VERTICAL_MARGIN = 10
        self._size = (self.get_parent().get_allocation().width -
                      HR_HORIZONTAL_MARGIN,
                      HR_VERTICAL_MARGIN)
        return self._size
    

class RichTextHorizontalRule (RichTextAnchor):
    def __init__(self):
        RichTextAnchor.__init__(self)
        #self.add_view(None)

    def add_view(self, view):
        self._widgets[view] = RichTextSep()
        self._widgets[view].show()
        return self._widgets[view]
        
    def copy(self):
        return RichTextHorizontalRule()
       

class BaseImage (BaseWidget):
    """Subclasses gtk.Image to make an Image Widget that can be used within
       RichTextViewS"""

    def __init__(self, *args, **kargs):
        BaseWidget.__init__(self)
        self._img = gtk.Image(*args, **kargs)
        self._img.show()
        self.add(self._img)
    
    def highlight(self):
        self.drag_highlight()
    
    def unhighlight(self):
        self.drag_unhighlight()
    
    def set_from_pixbuf(self, pixbuf):
        self._img.set_from_pixbuf(pixbuf)
    
    def set_from_stock(self, stock, size):
        self._img.set_from_stock(stock, size)
    


def get_image_format(filename):
    """Returns the image format for a filename"""
    f, ext = os.path.splitext(filename)
    ext = ext.replace(u".", "").lower()
    if ext == "jpg":
        ext = "jpeg"
    return ext


class RichTextImage (RichTextAnchor):
    """An Image child widget in a RichTextView"""

    def __init__(self):
        RichTextAnchor.__init__(self)
        self._filename = None
        self._download = False
        self._pixbuf = None
        self._pixbuf_original = None
        self._size = [None, None]
        self._save_needed = False
        

    def __del__(self):
        for widget in self._widgets:
            widget.disconnect("destroy")
            widget.disconnect("button-press-event")


    def add_view(self, view):
        self._widgets[view] = BaseImage()
        self._widgets[view].connect("destroy", self._on_image_destroy)
        self._widgets[view].connect("button-press-event", self._on_clicked)

        if self._pixbuf is not None:
            self._widgets[view].set_from_pixbuf(self._pixbuf)
        
        return self._widgets[view]


    def is_valid(self):
        """Did the image successfully load an image"""
        return self._pixbuf is not None
    
    def set_filename(self, filename):
        """Sets the filename used for saving image"""
        self._filename = filename
    
    def get_filename(self):
        """Returns the filename used for saving image"""
        return self._filename

    def get_original_pixbuf(self):
        """Returns the pixbuf of the image at its original size (no scaling)"""
        return self._pixbuf_original

    def set_save_needed(self, save):
        """Sets whether image needs to be saved to disk"""
        self._save_needed = save

    def save_needed(self):
        """Returns True if image needs to be saved to disk"""
        return self._save_needed


    
    def write(self, filename):
        """Write image to file"""
        
        # TODO: make more checks on saving
        if self._pixbuf:
            ext = get_image_format(filename)
            self._pixbuf_original.save(filename, ext)
            self._save_needed = False
        

    def write_stream(self, stream, filename="image.png"):
        """
        Write image to stream
        'filename' is used to infer picture format only.
        """

        def write(buf):
            stream.write(buf)
            return True
        format = get_image_format(filename)
        self._pixbuf_original.save_to_callback(write, format)
        self._save_needed = False
        
        
    def copy(self):
        """Returns a new copy of the image"""
        
        img = RichTextImage()
        img.set_filename(self._filename)
        img._size = list(self.get_size())
        
        if self._pixbuf:
            img._pixbuf = self._pixbuf
            img._pixbuf_original = self._pixbuf_original
        else:
            img.set_no_image()

        return img


    #=====================================================
    # set image
    
    
    def set_from_file(self, filename):
        """Sets the image from a file"""

        # TODO: remove this assumption (perhaps save full filename, and
        # caller will basename() if necessary
        if self._filename is None:
            self._filename = os.path.basename(filename)
        
        try:
            self._pixbuf_original = gdk.pixbuf_new_from_file(filename)
            
        except Exception:
            # use missing image instead
            self.set_no_image()
        else:
            # successful image load, set its size
            self._pixbuf = self._pixbuf_original
            
            if self.is_size_set():
                self.scale(self._size[0], self._size[1], False)

            for widget in self.get_all_widgets().itervalues():
                widget.set_from_pixbuf(self._pixbuf)

    def set_from_stream(self, stream):

        loader = gtk.gdk.PixbufLoader()
        try:
            loader.write(stream.read())
            loader.close()
            self._pixbuf_original = loader.get_pixbuf()
        except Exception:
            self.set_no_image()
        else:
            # successful image load, set its size
            self._pixbuf = self._pixbuf_original

            if self.is_size_set():
                self.scale(self._size[0], self._size[1], False)

            for widget in self.get_all_widgets().itervalues():
                widget.set_from_pixbuf(self._pixbuf)


    def set_no_image(self):
        """Set the 'no image' icon"""
        for widget in self.get_all_widgets().itervalues():
            widget.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
        self._pixbuf_original = None
        self._pixbuf = None


    def set_from_pixbuf(self, pixbuf, filename=None):
        """Set the image from a pixbuf"""
        
        if filename is not None:
            self._filename = filename
        self._pixbuf = pixbuf
        self._pixbuf_original = pixbuf

        if self.is_size_set():
            self.scale(self._size[0], self._size[1], True)
        else:
            for widget in self.get_all_widgets().itervalues():
                widget.set_from_pixbuf(self._pixbuf)


    
    def set_from_url(self, url, filename=None):
        """Set image by url"""

        imgfile = None        

        try:
            # make local temp file
            f, imgfile = tempfile.mkstemp("", "image")
            os.close(f)

            if download_file(url, imgfile):
                self.set_from_file(imgfile)
                if filename is not None:
                    self.set_filename(filename)
                else:
                    self.set_filename(url)
            else:
                raise Exception("Could not download file")
        except Exception:
            self.set_no_image()
        
        # remove tempfile
        if imgfile and os.path.exists(imgfile):
            os.remove(imgfile)


    #======================
    # Image Scaling
                
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
                if self._pixbuf is not None and set_widget:
                    for widget in self.get_all_widgets().itervalues():
                        widget.set_from_pixbuf(self._pixbuf)
        
        elif self._pixbuf_original is not None:
            # perform scaling
            
            width2 = self._pixbuf_original.get_width()
            height2 = self._pixbuf_original.get_height()
            
            if width is None:
                factor = height / float(height2)
                width = int(factor * width2)
            if height is None:
                factor = width / float(width2)
                height = int(factor * height2)
            
            self._pixbuf = self._pixbuf_original.scale_simple(
                width, height, gtk.gdk.INTERP_BILINEAR)

            if set_widget:
                for widget in self.get_all_widgets().itervalues():
                    widget.set_from_pixbuf(self._pixbuf)

        if self._buffer is not None:
            self._buffer.set_modified(True)



    #==========================
    # GUI callbacks
    
    def _on_image_destroy(self, widget):
        for key, value in self._widgets.iteritems():
            if value == widget:
                del self._widgets[key]
                break
    
    def _on_clicked(self, widget, event):
        """Callback for when image is clicked"""
        
        if event.button == 1:
            # left click selects image
            widget.grab_focus()
            #self._widgets[None].grab_focus()
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

class RichTextFont (RichTextBaseFont):
    """Class for representing a font in a simple way"""
    
    def __init__(self):
        RichTextBaseFont.__init__(self)
        
        # TODO: remove hard-coding
        self.mods = {}
        self.justify = "left"
        self.family = "Sans"
        self.size = 10
        self.fg_color = ""
        self.bg_color = ""
        self.indent = 0
        self.par_type = "none"
        self.link = None


    def set_font(self, attr, tags, current_tags, tag_table):    
        # set basic font attr
        RichTextBaseFont.set_font(self, attr, tags, current_tags, tag_table)
        
        font = attr.font
        
        if font:
            # get font family
            self.family = font.get_family()

            # get size in points (get_size() returns pango units)
            #PIXELS_PER_PANGO_UNIT = 1024
            #self.size = font.get_size() // PIXELS_PER_PANGO_UNIT
            self.size = get_attr_size(attr)

            weight = font.get_weight()
            style = font.get_style()
        else:
            # TODO: replace this hard-coding
            self.family = "Sans"
            self.size = 10
            weight = pango.WEIGHT_NORMAL
            style = pango.STYLE_NORMAL
        
        
        # get colors
        self.fg_color = color_to_string(attr.fg_color)
        self.bg_color = color_to_string(attr.bg_color)

        mod_class = tag_table.get_tag_class("mod")

        tag_set = set(tags)
        
        # set modifications (current tags override)
        self.mods = {}
        for tag in mod_class.tags:
            self.mods[tag.get_property("name")] = (tag in current_tags or
                                                   tag in tag_set)
        self.mods["tt"] = (self.mods["tt"] or self.family == "Monospace")
        
        # set justification
        self.justify = RichTextJustifyTag.justify2name[attr.justification]
        
        # current tags override for family and size
        for tag in current_tags:
            if isinstance(tag, RichTextJustifyTag):
                self.justify = tag.get_justify()
            elif isinstance(tag, RichTextFamilyTag):
                self.family = tag.get_family()            
            elif isinstance(tag, RichTextSizeTag):
                self.size = tag.get_size()
            elif isinstance(tag, RichTextFGColorTag):
                self.fg_color = tag.get_color()
            elif isinstance(tag, RichTextBGColorTag):
                self.bg_color = tag.get_color()

                
        # set indentation info
        for tag in chain(tags, current_tags):
            if isinstance(tag, RichTextIndentTag):
                self.indent = tag.get_indent()
                self.par_type = tag.get_par_indent()

            elif isinstance(tag, RichTextLinkTag):
                self.link = tag

            
        
        

#=============================================================================

class RichTextBuffer (RichTextBaseBuffer):
    """
    TextBuffer specialized for rich text editing

    It builds upon the features of RichTextBaseBuffer
    - maintains undo/redo stacks

    Additional Features
    - manages specific child widget actions
      - images
      - horizontal rule
    - manages editing of indentation levels and bullet point lists
    - manages "current font" behavior    

    """
    
    def __init__(self, table=RichTextTagTable()):
        RichTextBaseBuffer.__init__(self, table)

        # indentation handler
        self._indent = IndentHandler(self)
        self.connect("ending-user-action", 
                     lambda w: self._indent.update_indentation())

        # font handler
        self.font_handler = FontHandler(self)
        self.font_handler.set_font_class(RichTextFont)
        self.font_handler.connect("font-change",
            lambda w, font: self.emit("font-change", font))
        
        # set of all anchors in buffer
        self._anchors = set()
        self._anchors_highlighted = set()
        #self._child_uninit = set()

        # anchors that still need to be added,
        # they are defferred because textview was not available at insert-time
        self._anchors_deferred = set() 
        
        
    def clear(self):
        """Clear buffer contents"""
        
        RichTextBaseBuffer.clear(self)
        self._anchors.clear()
        self._anchors_highlighted.clear()
        self._anchors_deferred.clear()


    def insert_contents(self, contents, it=None):
        """Inserts a content stream into the TextBuffer at iter 'it'"""

        if it is None:
            it = self.get_insert_iter()

        self.begin_user_action()        
        insert_buffer_contents(self, it,
                               contents,
                               add_child_to_buffer,
                               lookup_tag=lambda name:
                                   self.tag_table.lookup(name))
        self.end_user_action()


    def copy_contents(self, start, end):
        """Return a content stream for copying from iter start and end"""

        contents = iter(iter_buffer_contents(self, start, end, ignore_tag))

        # remove regions that can't be copied
        for item in contents:
            # NOTE: item = (kind, it, param)
            
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


    def on_paragraph_split(self, start, end):
        """Callback for when paragraphs split"""
        if self.is_interactive():
            self._indent.on_paragraph_split(start, end)

    def on_paragraph_merge(self, start, end):
        """Callback for when paragraphs merge"""
        if self.is_interactive():        
            self._indent.on_paragraph_merge(start, end)

    def on_paragraph_change(self, start, end):
        """Callback for when paragraph type changes"""
        if self.is_interactive():
            self._indent.on_paragraph_change(start, end)

    def is_insert_allowed(self, it, text=""):
        """Returns True if insertion is allowed at iter 'it'"""

        # ask the indentation manager whether the insert is allowed
        return self._indent.is_insert_allowed(it, text) and \
               it.can_insert(True)
    

    def _on_delete_range(self, textbuffer, start, end):

        # TODO: should I add something like this back?
        # let indent manager prepare the delete
        #if self.is_interactive():
        #    self._indent.prepare_delete_range(start, end)
        
        # call super class
        RichTextBaseBuffer._on_delete_range(self, textbuffer, start, end)
        
        # deregister any deleted anchors
        for kind, offset, param in iter_buffer_contents(
            self, start, end, ignore_tag):
            if kind == "anchor":
                child = param[0]
                self._anchors.remove(child)
                if child in self._anchors_highlighted:
                    self._anchors_highlighted.remove(child)

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
    

    #===============================================
    # font handler interface

    def update_current_tags(self, action):
        return self.font_handler.update_current_tags(action)

    def set_default_attr(self, attr):
        return self.font_handler.set_default_attr(attr)

    def get_default_attr(self):
        return self.font_handler.get_default_attr()

    def get_current_tags(self):
        return self.font_handler.get_current_tags()

    def set_current_tags(self, tags):
        return self.font_handler.set_current_tags(tags)

    def can_be_current_tag(self, tag):
        return self.font_handler.can_be_current_tag(tag)

    def toggle_tag_selected(self, tag, start=None, end=None):
        return self.font_handler.toggle_tag_selected(tag, start, end)

    def apply_tag_selected(self, tag, start=None, end=None):
        return self.font_handler.apply_tag_selected(tag, start, end)

    def remove_tag_selected(self, tag, start=None, end=None):
        return self.font_handler.remove_tag_selected(tag, start, end)

    def remove_tag_class_selected(self, tag, start=None, end=None):
        return self.font_handler.remove_tag_class_selected(tag, start, end)
    
    def clear_tag_class(self, tag, start, end):
        return self.font_handler.clear_tag_class(tag, start, end)

    def clear_current_tag_class(self, tag):
        return self.font_handler.clear_current_tag_class(tag)

    def get_font(self, font=None):
        return self.font_handler.get_font(font)

    
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

        # let textview, if attached know we added a child
        self._anchors_deferred.add(child)
        self.emit("child-added", child)
            
    
    def add_deferred_anchors(self, textview):
        """Add anchors that were deferred"""
        
        for child in self._anchors_deferred:
            # only add anchor if it is still present (hasn't been deleted)
            if child in self._anchors:
                self._add_child_at_anchor(child, textview)
        
        self._anchors_deferred.clear()


    def _add_child_at_anchor(self, child, textview):
        
        # skip children whose insertion was rejected
        if child.get_deleted():
            return

        # TODO: eventually use real view
        widget = child.add_view(textview)
        textview.add_child_at_anchor(widget, child)

        child.show()

    
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer at current position"""
        
        # set default filename
        if image.get_filename() is None:
            image.set_filename(filename)
        
        # insert image into buffer
        self.begin_user_action()
        it = self.get_insert_iter()
        self.add_child(it, image)
        image.show()
        self.end_user_action()


    def insert_hr(self):
        """Insert Horizontal Rule"""
        self.begin_user_action()

        it = self.get_insert_iter()
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
            filename2 = keepnote.get_unique_filename_list(filenames,
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
        

    #=============================================
    # links

    def get_tag_region(self, it, tag):
        """
        Get the start and end TextIters for tag occuring at TextIter it
        Assumes tag occurs at TextIter it
        """
        
        # get bounds of link tag
        start = it.copy()
        if tag not in it.get_toggled_tags(True):
            start.backward_to_tag_toggle(tag)

        end = it.copy()
        if tag not in it.get_toggled_tags(False):
            end.forward_to_tag_toggle(tag)

        return start, end
    

    def get_link(self, it=None):
        
        if it is None:
            # use cursor
            sel = self.get_selection_bounds()
            if len(sel) > 0:
                it = sel[0]
            else:
                it = self.get_insert_iter()

        for tag in chain(it.get_tags(), it.get_toggled_tags(False)):
            if isinstance(tag, RichTextLinkTag):
                start, end = self.get_tag_region(it, tag)
                return tag, start, end

        return None, None, None

    
    def set_link(self, url, start, end):

        if url is None:
            tag = self.tag_table.lookup(RichTextLinkTag.tag_name(""))
            self.font_handler.clear_tag_class(tag, start, end)
            return None
        else:
            tag = self.tag_table.lookup(RichTextLinkTag.tag_name(url))
            self.font_handler.apply_tag_selected(tag, start, end)
            return tag
        

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
            highlight = set(x[2][0] for x in 
                            iter_buffer_anchors(self, sel[0], sel[1]))
            for child in self._anchors_highlighted:
                if child not in highlight:
                    child.unhighlight()
            for child in highlight:
                child.highlight()
            self._anchors_highlighted = highlight
            
        else:
            # no selection, unselect all children
            for child in self._anchors_highlighted:
                child.unhighlight()
            self._anchors_highlighted.clear()



gobject.type_register(RichTextBuffer)
gobject.signal_new("child-added", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("child-activated", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("child-menu", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object, object, object))
gobject.signal_new("font-change", RichTextBuffer, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object,))

