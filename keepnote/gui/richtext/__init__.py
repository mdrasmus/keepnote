"""

    KeepNote
    General rich text editor that saves to HTML

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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
import codecs
import gettext
from itertools import chain
import os
import tempfile
import re
import random
import StringIO
import urlparse
import uuid
from xml.sax.saxutils import escape


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk
import gtk.keysyms   # this is necessary for py2exe discovery

# try to import spell check
try:
    import gtkspell
except ImportError:
    gtkspell = None


# textbuffer_tools imports
from .textbuffer_tools import \
     iter_buffer_contents, iter_buffer_anchors, sanitize_text

# richtextbuffer imports
from .richtextbuffer import \
     ignore_tag, \
     add_child_to_buffer, \
     RichTextBuffer, \
     RichTextImage, \
     RichTextIndentTag

# tag imports
from .richtext_tags import \
     RichTextModTag, \
     RichTextJustifyTag, \
     RichTextFamilyTag, \
     RichTextSizeTag, \
     RichTextFGColorTag, \
     RichTextBGColorTag, \
     RichTextIndentTag, \
     RichTextBulletTag, \
     RichTextLinkTag, \
     get_text_scale, \
     set_text_scale

# richtext io
from .richtext_html import HtmlBuffer, HtmlError


import keepnote
from keepnote import translate as _



#=============================================================================
# constants
DEFAULT_FONT = "Sans 10"
TEXTVIEW_MARGIN = 5
if keepnote.get_platform() == "darwin":
    CLIPBOARD_NAME = gdk.SELECTION_PRIMARY
else:
    CLIPBOARD_NAME = "CLIPBOARD"
RICHTEXT_ID = -3    # application defined integer for the clipboard
CONTEXT_MENU_ACCEL_PATH = "<main>/richtext_context_menu"
QUOTE_FORMAT = u'from <a href="%u">%t</a>:<br/>%s'

# mime types
# richtext mime type is process specific
MIME_RICHTEXT = "application/x-richtext" + str(random.randint(1, 100000))
MIME_IMAGES = ["image/png",
               "image/bmp",
               "image/jpeg",
               "image/xpm",

               # Mac OS X MIME types
               "public.png",
               "public.bmp",
               "public.jpeg",
               "public.xpm"]


# TODO: add more text MIME types?
MIME_TEXT = ["text/plain",
             "text/plain;charset=utf-8",
             "text/plain;charset=UTF-8",
             "UTF8_STRING",
             "STRING",
             "COMPOUND_TEXT",
             "TEXT"]

MIME_HTML = ["HTML Format",
             "text/html"]


# globals
_g_clipboard_contents = None



def parse_font(fontstr):
    """Parse a font string from the font chooser"""
    tokens = fontstr.split(" ")
    size = int(tokens.pop())
    mods = []
        
    # NOTE: underline is not part of the font string and is handled separately
    while tokens[-1] in ["Bold", "Italic"]:
        mods.append(tokens.pop().lower())
        
    return " ".join(tokens), mods, size


def parse_utf(text):

    # TODO: lookup the standard way to do this
    
    if text[:2] in (codecs.BOM_UTF16_BE, codecs.BOM_UTF16_LE) or (
        len(text) > 1 and text[1] == '\x00') or (
        len(text) > 3 and text[3] == '\x00'):
        return text.decode("utf16")
    else:
        text = text.replace("\x00", "")
        return unicode(text, "utf8")


def parse_ie_html_format(text):
    """Extract HTML from IE's 'HTML Format' clipboard data"""
    index = text.find("<!--StartFragment")
    if index == -1:
        return None
    index = text.find(">", index)
    return text[index+1:]

def parse_ie_html_format_headers(text):
    headers = {}
    for line in text.splitlines():
        if line.startswith("<"):
            break
        i = line.find(":")
        if i == -1:
            break
        key = line[:i]
        val = line[i+1:]
        headers[key] = val
    return headers


def parse_richtext_headers(text):
    headers = {}
    for line in text.splitlines():
        i = line.find(":")
        if i > -1:
            headers[line[:i]] = line[i+1:]
    return headers


def format_richtext_headers(values):
    return "\n".join(key + ":" + val.replace("\n", "") for key, val in values)


def is_relative_file(filename):
    """Returns True if filename is relative"""
    
    return (not re.match("[^:/]+://", filename) and 
            not os.path.isabs(filename))


def replace_vars(text, values):

    textlen = len(text)
    out = []
    i = 0

    while i < textlen:
        if text[i] == "\\" and i < textlen - 1:
            # escape
            out.append(text[i+1])
            i += 2

        elif text[i] == "%" and i < textlen - 1:
            # variable
            varname = text[i:i+2]
            out.append(values.get(varname, ""))
            i += 2

        else:
            # literal
            out.append(text[i])
            i += 1

    return "".join(out)


#=============================================================================


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


class RichTextMenu (gtk.Menu):
    """A popup menu for child widgets in a RichTextView"""
    def __inti__(self):
        gkt.Menu.__init__(self)
        self._child = None

    def set_child(self, child):
        self._child = child

    def get_child(self):
        return self._child


class RichTextIO (object):
    """Read/Writes the contents of a RichTextBuffer to disk"""

    def __init__(self):
        self._html_buffer = HtmlBuffer()

    
    def save(self, textbuffer, filename, title=None, stream=None):
        """
        Save buffer contents to file

        textbuffer -- richtextbuffer to save
        filename   -- HTML filename to save to (optional if stream given)
        title      -- title of HTML file (optional)
        stream     -- output stream for HTML file (optional)
        """
        
        self._save_images(textbuffer, filename)
        
        try:
            buffer_contents = iter_buffer_contents(
                textbuffer, None, None, ignore_tag)
            
            if stream:
                out = stream
            else:
                out = codecs.open(filename, "w", "utf-8")
            self._html_buffer.set_output(out)
            self._html_buffer.write(buffer_contents,
                                    textbuffer.tag_table,
                                    title=title)
            out.close()
        except IOError, e:
            raise RichTextError("Could not save '%s'." % filename, e)
        
        textbuffer.set_modified(False)
    
    
    def load(self, textview, textbuffer, filename, stream=None):
        """
        Load buffer with data from file

        textbuffer -- richtextbuffer to load
        filename   -- HTML filename to load (optional if stream given)
        stream     -- output stream for HTML file (optional)
        """
        
        # unhook expensive callbacks
        textbuffer.block_signals()
        if textview:
            spell = textview.is_spell_check_enabled()
            textview.enable_spell_check(False)
            textview.set_buffer(None)


        # clear buffer        
        textbuffer.clear()
        
        err = None
        try:
            if stream:
                infile = stream
            else:
                infile = codecs.open(filename, "r", "utf-8")
            buffer_contents = self._html_buffer.read(infile)
            textbuffer.insert_contents(buffer_contents,
                                       textbuffer.get_start_iter())
            infile.close()

            # put cursor at begining
            textbuffer.place_cursor(textbuffer.get_start_iter())
            
        except (HtmlError, IOError, Exception), e:
            err = e
            textbuffer.clear()
            if textview:
                textview.set_buffer(textbuffer)
            ret = False            
        else:
            # finish loading
            self._load_images(textbuffer, filename)
            if textview:
                textview.set_buffer(textbuffer)
                textview.show_all()
            ret = True
        
        # rehook up callbacks
        textbuffer.unblock_signals()
        if textview:
            textview.enable_spell_check(spell)
            textview.enable()
        
        textbuffer.set_modified(False)
        
        # reraise error
        if not ret:
            raise RichTextError("Error loading '%s'." % filename, e)
        

    
    def _load_images(self, textbuffer, html_filename):
        """Load images present in textbuffer"""
        
        for kind, it, param in iter_buffer_anchors(textbuffer, None, None):
            child, widgets = param
            if isinstance(child, RichTextImage):
                self._load_image(textbuffer, child, html_filename)

    
    def _save_images(self, textbuffer, html_filename):
        """Save images present in text buffer"""

        for kind, it, param in iter_buffer_anchors(textbuffer, None, None):
            child, widgets = param
            if isinstance(child, RichTextImage):
                self._save_image(textbuffer, child, html_filename)


    def _load_image(self, textbuffer, image, html_filename):
        image.set_from_file(
            self._get_filename(html_filename, image.get_filename()))

    def _save_image(self, textbuffer, image, html_filename):
        if child.save_needed():
            image.write(self._get_filename(html_filename, image.get_filename()))

    def _get_filename(self, html_filename, filename):
        if is_relative_file(filename):
            path = os.path.dirname(html_filename)
            return os.path.join(path, filename)
        return filename

                    

class RichTextDragDrop (object):
    """Manages drag and drop events for a richtext editor"""

    def __init__(self, targets=[]):
        self._acceptable_targets = []
        self._acceptable_targets.extend(targets)

    def append_target(self, target):
        self._acceptable_targets.append(target)

    def extend_targets(self, targets):
        self._acceptable_targets.extend(target)

    def find_acceptable_target(self, targets):
        
        for target in self._acceptable_targets:
            if target in targets:
                return target
        return None
        




class RichTextView (gtk.TextView):
    """A RichText editor widget"""

    def __init__(self, textbuffer=None):
        gtk.TextView.__init__(self, textbuffer)

        self._textbuffer = None
        self._buffer_callbacks = []
        self._blank_buffer = RichTextBuffer()
        self._popup_menu = None
        self._html_buffer = HtmlBuffer()
        self._accel_group = None
        self._accel_path = CONTEXT_MENU_ACCEL_PATH
        self.dragdrop = RichTextDragDrop(MIME_IMAGES +  ["text/uri-list"] +
                                         MIME_HTML + MIME_TEXT)
        self._quote_format = QUOTE_FORMAT
        self._current_url = ""
        self._current_title = ""

        if textbuffer is None:
            textbuffer = RichTextBuffer() 
        self.set_buffer(textbuffer)

        self.set_default_font(DEFAULT_FONT)
        
        
        # spell checker
        self._spell_checker = None
        self.enable_spell_check(True)
        
        # signals        
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.set_property("right-margin", TEXTVIEW_MARGIN)
        self.set_property("left-margin", TEXTVIEW_MARGIN)

        self.connect("key-press-event", self.on_key_press_event)
        #self.connect("insert-at-cursor", self.on_insert_at_cursor)
        self.connect("backspace", self.on_backspace)
        self.connect("button-press-event", self.on_button_press)

        # drag and drop
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("drag-motion", self.on_drag_motion)
        self.connect("drag-data-get", self.on_drag_data_get)
        self.drag_dest_add_image_targets()

        # clipboard
        self.connect("copy-clipboard", lambda w: self._on_copy())
        self.connect("cut-clipboard", lambda w: self._on_cut())
        self.connect("paste-clipboard", lambda w: self._on_paste())

        #self.connect("button-press-event", self.on_button_press)
        self.connect("populate-popup", self.on_popup)

        
        # popup menus
        self.init_menus()
        
        # requires new pygtk
        #self._textbuffer.register_serialize_format(MIME_TAKENOTE, 
        #                                          self.serialize, None)
        #self._textbuffer.register_deserialize_format(MIME_TAKENOTE, 
        #                                            self.deserialize, None)


    def init_menus(self):
        """Initialize popup menus"""
        
        # image menu
        self._image_menu = RichTextMenu()
        self._image_menu.attach_to_widget(self, lambda w,m:None)

        item = gtk.ImageMenuItem(gtk.STOCK_CUT)
        item.connect("activate", lambda w: self.emit("cut-clipboard"))
        self._image_menu.append(item)
        item.show()
        
        item = gtk.ImageMenuItem(gtk.STOCK_COPY)
        item.connect("activate", lambda w: self.emit("copy-clipboard"))
        self._image_menu.append(item)
        item.show()

        item = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        def func(widget):
            if self._textbuffer:
                self._textbuffer.delete_selection(True, True)
        item.connect("activate", func)
        self._image_menu.append(item)
        item.show()

    
    
    def set_buffer(self, textbuffer):
        """Attach this textview to a RichTextBuffer"""
        
        # tell current buffer we are detached
        if self._textbuffer:
            for callback in self._buffer_callbacks:
                self._textbuffer.disconnect(callback)

        
        # change buffer
        if textbuffer:
            gtk.TextView.set_buffer(self, textbuffer)            
        else:
            gtk.TextView.set_buffer(self, self._blank_buffer)
        self._textbuffer = textbuffer


        # tell new buffer we are attached
        if self._textbuffer:
            self._textbuffer.set_default_attr(self.get_default_attributes())
            self._modified_id = self._textbuffer.connect(
                "modified-changed", self._on_modified_changed)

            self._buffer_callbacks = [
                self._textbuffer.connect("font-change",
                                        self._on_font_change),
                self._textbuffer.connect("child-added",
                                         self._on_child_added),
                self._textbuffer.connect("child-activated",
                                        self._on_child_activated),
                self._textbuffer.connect("child-menu",
                                        self._on_child_popup_menu),
                self._modified_id
                ]
            
            # add all deferred anchors
            self._textbuffer.add_deferred_anchors(self)


    def set_accel_group(self, accel_group):
        self._accel_group = accel_group


    def set_accel_path(self, accel_path):
        self._accel_path = accel_path


    def set_current_url(self, url, title=""):
        self._current_url = url
        self._current_title = title


    def get_current_url(self):
        return self._current_url


    #======================================================
    # keyboard callbacks


    def on_key_press_event(self, textview, event):
        """Callback from key press event"""

        if self._textbuffer is None:
            return

        if event.keyval == gtk.keysyms.ISO_Left_Tab:
            # shift+tab is pressed

            it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())

            # indent if there is a selection
            if self._textbuffer.get_selection_bounds():
                # tab at start of line should do unindentation
                self.unindent()
                return True

        if event.keyval == gtk.keysyms.Tab:
            # tab is pressed
            
            it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())

            # indent if cursor at start of paragraph or if there is a selection
            if self._textbuffer.starts_par(it) or \
               self._textbuffer.get_selection_bounds():
                # tab at start of line should do indentation
                self.indent()
                return True


        if event.keyval == gtk.keysyms.Delete:
            # delete key pressed

            # TODO: make sure selection with delete does not fracture
            # unedititable regions.
            it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())

            if not self._textbuffer.get_selection_bounds() and \
               self._textbuffer.starts_par(it) and \
               not self._textbuffer.is_insert_allowed(it) and \
               self._textbuffer.get_indent(it)[0] > 0:
                # delete inside bullet phrase, removes bullet
                self.toggle_bullet("none")
                self.unindent()
                return True



    def on_backspace(self, textview):
        """Callback for backspace press"""

        if not self._textbuffer:
            return

        it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())

        if self._textbuffer.starts_par(it):
            # look for indent tags
            indent, par_type = self._textbuffer.get_indent()
            if indent > 0:
                self.unindent()
                self.stop_emission("backspace")
                        

    #==============================================
    # callbacks


    def on_button_press(self, widget, event):
        """Process context popup menu"""

        
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            # double left click
            
            x, y = self.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                                int(event.x), int(event.y))
            it = self.get_iter_at_location(x, y)

            if self.click_iter(it):
                self.stop_emission("button-press-event")
            

    def click_iter(self, it=None):
        """Perfrom click action at TextIter it"""

        if not self._textbuffer:
            return

        if it is None:            
            it = self._textbuffer.get_insert_iter()

        for tag in chain(it.get_tags(), it.get_toggled_tags(False)):
            if isinstance(tag, RichTextLinkTag):
                self.emit("visit-url", tag.get_href())
                return True

        return False

    

    #=======================================================
    # Drag and drop

    def on_drag_motion(self, textview, drag_context, x, y, timestamp):
        """Callback for when dragging over textview"""

        if not self._textbuffer:
            return

        target = self.dragdrop.find_acceptable_target(drag_context.targets)
        if target:
            textview.drag_dest_set_target_list([(target, 0, 0)])

    
    
    def on_drag_data_received(self, widget, drag_context, x, y,
                              selection_data, info, eventtime):
        """Callback for when drop event is received"""

        if not self._textbuffer:
            return
        
        #TODO: make this pluggable.
        
        target = self.dragdrop.find_acceptable_target(drag_context.targets)
        
        if target in MIME_IMAGES:
            # process image drop
            pixbuf = selection_data.get_pixbuf()
            
            if pixbuf != None:
                image = RichTextImage()
                image.set_from_pixbuf(pixbuf)
        
                self.insert_image(image)
            
                drag_context.finish(True, True, eventtime)
                self.stop_emission("drag-data-received")

        elif target == "text/uri-list":
            # process URI drop

            uris = parse_utf(selection_data.data)

            # remove empty lines and comments
            uris = [x for x in (uri.strip()
                                for uri in uris.split("\n"))
                    if len(x) > 0 and x[0] != "#"]

            links = ['<a href="%s">%s</a> ' % (uri, uri) for uri in uris]

            # insert links
            self.insert_html("<br />".join(links))
            
                
        elif target in MIME_HTML:
            # process html drop

            html = parse_utf(selection_data.data)
            if taget == "HTML Format":
                # skip over headers
                html = html[html.find("\r\n\r\n")+4:]

            self.insert_html(html)
            
        
        elif target in MIME_TEXT:
            # process text drop
            self._textbuffer.insert_at_cursor(selection_data.get_text())



    def on_drag_data_get(self, widget, drag_context, selection_data,
                             info, timestamp):
        """
        Callback for when data is requested by drag_get_data
        """

        return

        '''
        # override gtk's data get code
        self.stop_emission("drag-data-get")

        sel = self._textbuffer.get_selection_bounds()

        # do nothing if nothing is selected
        if not sel:
            text = ""
        else:
            start, end = sel
            text = start.get_text(end)
        print "get", repr(text)
        selection_data.set_text(text.encode("utf8"), -1)
        
        #self.emit("cut-clipboard")
        '''


    
    #==================================================================
    # Copy and Paste

    def _on_copy(self):
        """Callback for copy action"""
        clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)
        self.stop_emission('copy-clipboard')
        self.copy_clipboard(clipboard)

    
    def _on_cut(self):
        """Callback for cut action"""    
        clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)
        self.stop_emission('cut-clipboard')
        self.cut_clipboard(clipboard, self.get_editable())

    
    def _on_paste(self):
        """Callback for paste action"""
        
        clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)
        self.stop_emission('paste-clipboard')
        self.paste_clipboard(clipboard, None, self.get_editable())
        

    def copy_clipboard(self, clipboard):
        """Callback for copy event"""

        #clipboard.set_can_store(None)

        if not self._textbuffer:
            return
    
        sel = self._textbuffer.get_selection_bounds()

        # do nothing if nothing is selected
        if not sel:
            return
        
        start, end = sel
        contents = list(self._textbuffer.copy_contents(start, end))
        headers = format_richtext_headers([
                    ("title", self._current_title),
                    ("url", self._current_url)])
        
        if len(contents) == 1 and \
           contents[0][0] == "anchor" and \
           isinstance(contents[0][2][0], RichTextImage):
            # copy image
            targets = [(MIME_RICHTEXT, gtk.TARGET_SAME_APP, RICHTEXT_ID)] + \
                [("text/x-moz-url-priv", 0, RICHTEXT_ID)] + \
                [("text/html", 0, RICHTEXT_ID)] + \
                [(x, 0, RICHTEXT_ID) for x in MIME_IMAGES]
            
            clipboard.set_with_data(targets, self._get_selection_data, 
                                    self._clear_selection_data,
                                    (headers, contents, ""))

        else:
            # copy text
            targets = [(MIME_RICHTEXT, gtk.TARGET_SAME_APP, RICHTEXT_ID)] + \
                [("text/x-moz-url-priv", 0, RICHTEXT_ID)] + \
                [("text/html", 0, RICHTEXT_ID)] + \
                [(x, 0, RICHTEXT_ID) for x in MIME_TEXT]
            
            text = start.get_text(end)
            clipboard.set_with_data(targets, self._get_selection_data, 
                                    self._clear_selection_data,
                                    (headers, contents, text))



    def cut_clipboard(self, clipboard, default_editable):
        """Callback for cut event"""

        if not self._textbuffer:
            return
        
        self.copy_clipboard(clipboard)
        self._textbuffer.delete_selection(True, default_editable)

    
    def paste_clipboard(self, clipboard, override_location, default_editable):
        """Callback for paste event"""

        if not self._textbuffer:
            return
        
        # get available targets for paste
        targets = clipboard.wait_for_targets()
        if targets is None:
            return
        targets = set(targets)
        
        # check that insert is allowed
        it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())
        if not self._textbuffer.is_insert_allowed(it):            
            return

        # try to paste richtext
        if MIME_RICHTEXT in targets:
            clipboard.request_contents(MIME_RICHTEXT, self._do_paste_object)
            return
        
        # try to paste html
        for mime_html in MIME_HTML:
            if mime_html in targets:
                if mime_html == "HTML Format":
                    clipboard.request_contents(mime_html, 
                                               self._do_paste_html_headers)
                else:
                    clipboard.request_contents(mime_html, self._do_paste_html)
                return

        # try to paste image
        for mime_image in MIME_IMAGES:
            if mime_image in targets:
                clipboard.request_contents(mime_image, self._do_paste_image)
                return

        # paste plain text as last resort
        clipboard.request_text(self._do_paste_text)

    
    def paste_clipboard_as_text(self):
        """Callback for paste action"""    
        clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)

        if not self._textbuffer:
            return
        
        targets = clipboard.wait_for_targets()
        if targets is None:
            # nothing on clipboard
            return
        
        # check that insert is allowed
        it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())
        if not self._textbuffer.is_insert_allowed(it):            
            return

        # request text
        clipboard.request_text(self._do_paste_text)


    def paste_clipboard_as_quote(self, plain_text=False):
        """Callback for paste action"""    
        clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)
        
        quote_format = self._quote_format

        if not self._textbuffer:
            return
        
        targets = clipboard.wait_for_targets()
        if targets is None:
            # nothing on clipboard
            return
        
        # check that insert is allowed
        it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())
        if not self._textbuffer.is_insert_allowed(it):            
            return

        if MIME_RICHTEXT in targets:
            selection_data = clipboard.wait_for_contents(MIME_RICHTEXT)
            headers = parse_richtext_headers(parse_utf(selection_data.data))
            url = headers.get("url")
            title = headers.get("title")
        elif "text/x-moz-url-priv" in targets:
            selection_data = clipboard.wait_for_contents("text/x-moz-url-priv")
            url = parse_utf(selection_data.data)
            url = url.strip("\n\r\0")
            title = None
        elif "HTML Format" in targets:
            selection_data = clipboard.wait_for_contents("HTML Format")
            headers = parse_ie_html_format_headers(
                parse_utf(selection_data.data))
            url = headers.get("SourceURL")
            title = None
        else:
            url = None
            title = None

        # setup variables
        if url is not None:
            parts = urlparse.urlsplit(url)
            url = url
            if parts.hostname:
                host = parts.hostname
            else:
                host = u"unknown source"
        else:
            url = u""
            host = u"unknown source"
        unique = str(uuid.uuid4())

        if title is None:
            title = host

        # replace variables
        quote_format = replace_vars(quote_format, {"%u": escape(url), 
                                                   "%t": escape(title),
                                                   "%s": unique})
        
        # prepare quote data
        contents = self.parse_html(quote_format)
        before = []
        after = []
        for i, item in enumerate(contents):
            if item[0] == "text":
                text = item[2]
                if unique in text:
                    j = text.find(unique)
                    before.append(("text", item[1], text[:j]))
                    after = [("text", item[1], text[j+len(unique):])]
                    after.extend(contents[i+1:])
                    break
            before.append(item)

        # TODO: paste is not considered a single action yet
        
        # perform paste of contents
        self._textbuffer.begin_user_action()
        offset1 = it.get_offset()
        if plain_text:
            self.paste_clipboard_as_text()
        else:
            self.paste_clipboard(clipboard, False, True)
        end = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())
        start = self._textbuffer.get_iter_at_offset(offset1)

        # get pasted contents
        contents2 = list(iter_buffer_contents(self._textbuffer, start, end))
        
        # repaste with quote
        self._textbuffer.delete(start, end)
        self._textbuffer.insert_contents(before)
        self._textbuffer.insert_contents(contents2)
        self._textbuffer.insert_contents(after)
        self._textbuffer.end_user_action()




    
    def _do_paste_text(self, clipboard, text, data):
        """Paste text into buffer"""
        
        if text is None:
            return
        
        self._textbuffer.begin_user_action()
        self._textbuffer.delete_selection(False, True)
        self._textbuffer.insert_at_cursor(sanitize_text(text))
        self._textbuffer.end_user_action()

        self.scroll_mark_onscreen(self._textbuffer.get_insert())

    def _do_paste_html(self, clipboard, selection_data, data):
        """Paste HTML into buffer"""

        html = parse_utf(selection_data.data)        
        self._paste_html(html)


    def _do_paste_html_headers(self, clipboard, selection_data, data):
        """Paste 'HTML Format' into buffer"""

        html = parse_utf(selection_data.data)
        html = parse_ie_html_format(html)
        self._paste_html(html)


    def _paste_html(self, html):
        """Perform paste of HTML from string"""

        try:
            self._textbuffer.begin_user_action()
            self._textbuffer.delete_selection(False, True)
            self.insert_html(html)
            self._textbuffer.end_user_action()
        
            self.scroll_mark_onscreen(self._textbuffer.get_insert())
        except Exception, e:
            pass
            
    
    def _do_paste_image(self, clipboard, selection_data, data):
        """Paste image into buffer"""

        pixbuf = selection_data.get_pixbuf()
        image = RichTextImage()
        image.set_from_pixbuf(pixbuf)

        self._textbuffer.begin_user_action()
        self._textbuffer.delete_selection(False, True)
        self._textbuffer.insert_image(image)
        self._textbuffer.end_user_action()
        self.scroll_mark_onscreen(self._textbuffer.get_insert())
        
    
    def _do_paste_object(self, clipboard, selection_data, data):
        """Paste a program-specific object into buffer"""
        
        if _g_clipboard_contents is None:
            # do nothing
            return

        self._textbuffer.begin_user_action()
        self._textbuffer.delete_selection(False, True)
        self._textbuffer.insert_contents(_g_clipboard_contents)
        self._textbuffer.end_user_action()
        self.scroll_mark_onscreen(self._textbuffer.get_insert())        
    
    
    def _get_selection_data(self, clipboard, selection_data, info, data):
        """Callback for when Clipboard needs selection data"""

        
        global _g_clipboard_contents

        headers, contents, text = data
        
        _g_clipboard_contents = contents

        if "text/x-moz-url-priv" in selection_data.target:
            selection_data.set("text/x-moz-url-priv", 8, self._current_url)
        
        elif MIME_RICHTEXT in selection_data.target:
            # set rich text
            selection_data.set(MIME_RICHTEXT, 8, headers)
            
        elif "text/html" in selection_data.target:
            # set html
            stream = StringIO.StringIO()
            self._html_buffer.set_output(stream)
            self._html_buffer.write(contents,
                                    self._textbuffer.tag_table,
                                    partial=True,
                                    xhtml=False)
            selection_data.set("text/html", 8, stream.getvalue())

        elif len([x for x in MIME_IMAGES
                  if x in selection_data.target]) > 0:
            # set image
            image = contents[0][2][0]
            selection_data.set_pixbuf(image.get_original_pixbuf())
            
        else:
            # set plain text
            selection_data.set_text(text)

    
    def _clear_selection_data(self, clipboard, data):
        """Callback for when Clipboard contents are reset"""
        global _g_clipboard_contents
        _g_clipboard_contents = None
                    

    def set_quote_format(self, format):
        self._quote_format = format

    def get_quote_format(self):
        return self._quote_format



    #=============================================
    # State
    
    def is_modified(self):
        """Returns True if buffer is modified"""

        if self._textbuffer:            
            return self._textbuffer.get_modified()
        else:
            return False

    
    def _on_modified_changed(self, textbuffer):
        """Callback for when buffer is modified"""
        
        # propogate modified signal to listeners of this textview
        self.emit("modified", textbuffer.get_modified())


        
    def enable(self):
        self.set_sensitive(True)
    
    
    def disable(self):
        """Disable TextView"""

        if self._textbuffer:
            self._textbuffer.handler_block(self._modified_id)
            self._textbuffer.clear()
            self._textbuffer.set_modified(False)
            self._textbuffer.handler_unblock(self._modified_id)

        self.set_sensitive(False)
        
    
    """
    def serialize(self, register_buf, content_buf, start, end, data):
        print "serialize", content_buf
        self.a = u"SERIALIZED"
        return self.a 
    
    
    def deserialize(self, register_buf, content_buf, it, data, create_tags, udata):
        print "deserialize"
    """

    #=====================================================
    # Popup Menus

    
    def on_popup(self, textview, menu):
        """Popup menu for RichTextView"""
        
        self._popup_menu = menu        

        # position of 'paste' option
        pos = 3

        # insert additional menu options after paste
        item = gtk.ImageMenuItem(stock_id=gtk.STOCK_PASTE, accel_group=None)
        item.child.set_text(_("Paste As Plain Text"))
        item.connect("activate", lambda item: self.paste_clipboard_as_text())
        item.show()
        menu.insert(item, pos)

        item = gtk.ImageMenuItem(stock_id=gtk.STOCK_PASTE, accel_group=None)
        item.child.set_text(_("Paste As Quote"))
        item.connect("activate", lambda item: self.paste_clipboard_as_quote())
        item.show()
        menu.insert(item, pos+1)

        item = gtk.ImageMenuItem(stock_id=gtk.STOCK_PASTE, accel_group=None)
        item.child.set_text(_("Paste As Plain Text Quote"))
        item.connect("activate", 
            lambda item: self.paste_clipboard_as_quote(plain_text=True))
        item.show()
        menu.insert(item, pos+2)

        menu.set_accel_path(self._accel_path)
        if self._accel_group:
            menu.set_accel_group(self._accel_group)

    

    def _on_child_popup_menu(self, textbuffer, child, button, activate_time):
        """Callback for when child menu should appear"""
        self._image_menu.set_child(child)

        # popup menu based on child widget
        if isinstance(child, RichTextImage):
            # image menu
            self._image_menu.popup(None, None, None, button, activate_time)
            self._image_menu.show()

            
    def get_image_menu(self):
        """Returns the image popup menu"""
        return self._image_menu

    def get_popup_menu(self):
        """Returns the popup menu"""
        return self._popup_menu


    #==========================================
    # child events

    def _on_child_added(self, textbuffer, child):
        """Callback when child added to buffer"""
        self._add_children()
                               

    def _on_child_activated(self, textbuffer, child):
        """Callback for when child has been activated"""
        self.emit("child-activated", child)
        
    
    #===========================================================
    # Actions

    def _add_children(self):
        """Add all deferred children in textbuffer"""        
        self._textbuffer.add_deferred_anchors(self)
        

    def indent(self):
        """Indents selection one more level"""
        if self._textbuffer:
            self._textbuffer.indent()


    def unindent(self):
        """Unindents selection one more level"""        
        if self._textbuffer:
            self._textbuffer.unindent()

    
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer"""
        if self._textbuffer:
            self._textbuffer.insert_image(image, filename)    

    def insert_image_from_file(self, imgfile, filename="image.png"):
        """Inserts an image from a file"""
        
        pixbuf = gdk.pixbuf_new_from_file(imgfile)
        img = RichTextImage()
        img.set_from_pixbuf(pixbuf)
        self.insert_image(img, filename)

    def insert_hr(self):
        """Inserts a horizontal rule"""
        if self._textbuffer:
            self._textbuffer.insert_hr()
        
        
    def insert_html(self, html):
        """Insert HTML content into Buffer"""

        if self._textbuffer:
            self._textbuffer.insert_contents(self.parse_html(html))


    def parse_html(self, html):
        
        contents = list(self._html_buffer.read(
                StringIO.StringIO(html), partial=True, ignore_errors=True))

        # scan contents
        for kind, pos, param in contents:
            # download images included in html
            if kind == "anchor" and isinstance(param[0], RichTextImage):
                img = param[0]
                filename = img.get_filename()
                if filename and (filename.startswith("http:") or 
                                 filename.startswith("file:")):
                    try:
                        img.set_from_url(filename, "image.png")
                    except:
                        # Be robust to errors from loading from the web.
                        pass
        
        return contents


    def get_link(self, it=None):

        if self._textbuffer is None:
            return None, None, None
        return self._textbuffer.get_link(it)

    
    def set_link(self, url="", start=None, end=None):
        if self._textbuffer is None:
            return

        if start is None or end is None:
            tagname = RichTextLinkTag.tag_name(url)
            self._apply_tag(tagname)
            return self._textbuffer.tag_table.lookup(tagname)
        else:
            return self._textbuffer.set_link(url, start, end)
                

    #==========================================================
    # Find/Replace
    
    def forward_search(self, it, text, case_sensitive, wrap=True):
        """Finds next occurrence of 'text' searching forwards"""
        
        it = it.copy()
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
                if wrap:
                    return self.forward_search(self._textbuffer.get_start_iter(),
                                               text, case_sensitive, False)
                else:
                    return None
    
    
    def backward_search(self, it, text, case_sensitive, wrap=True):
        """Finds next occurrence of 'text' searching backwards"""
        
        it = it.copy()
        it.backward_char()
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
                if wrap:
                    return self.backward_search(self._textbuffer.get_end_iter(),
                                                text, case_sensitive, False)
                else:
                    return None

        
    
    def find(self, text, case_sensitive=False, forward=True, next=True):
        """Finds next occurrence of 'text'"""
        
        if not self._textbuffer:
            return
        
        it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())
        
        
        if forward:
            if next:
                it.forward_char()
            result = self.forward_search(it, text, case_sensitive)
        else:
            result = self.backward_search(it, text, case_sensitive)
        
        if result:
            self._textbuffer.select_range(result[0], result[1])
            self.scroll_mark_onscreen(self._textbuffer.get_insert())
            return result[0].get_offset()
        else:
            return -1
        
        
    def replace(self, text, replace_text, 
                case_sensitive=False, forward=True, next=False):
        """Replaces next occurrence of 'text' with 'replace_text'"""

        if not self._textbuffer:
            return
        
        pos = self.find(text, case_sensitive, forward, next)
        
        if pos != -1:
            self._textbuffer.begin_user_action()
            self._textbuffer.delete_selection(True, self.get_editable())
            self._textbuffer.insert_at_cursor(replace_text)
            self._textbuffer.end_user_action()
            
        return pos
        
            
    def replace_all(self, text, replace_text, 
                    case_sensitive=False, forward=True):
        """Replaces all occurrences of 'text' with 'replace_text'"""

        if not self._textbuffer:
            return
        
        found = False
        
        self._textbuffer.begin_user_action()
        while self.replace(text, replace_text, case_sensitive, forward, False) != -1:
            found = True
        self._textbuffer.end_user_action()
        
        return found

    #===========================================================
    # Spell check
    
    def can_spell_check(self):
        """Returns True if spelling is available"""
        return gtkspell is not None
    
    def enable_spell_check(self, enabled=True):
        """Enables/disables spell check"""
        if not self.can_spell_check():
            return
        
        if enabled:
            if self._spell_checker is None:
                try:
                    self._spell_checker = gtkspell.Spell(self)
                except Exception:
                    # unable to intialize spellcheck, abort
                    self._spell_checker = None
        else:
            if self._spell_checker is not None:
                self._spell_checker.detach()
                self._spell_checker = None

    def is_spell_check_enabled(self):
        """Returns True if spell check is enabled"""
        return self._spell_checker is not None
        
    #===========================================================
    # font manipulation

    def _apply_tag(self, tag_name):
        if self._textbuffer:
            self._textbuffer.apply_tag_selected(
                self._textbuffer.tag_table.lookup(tag_name))

    def toggle_font_mod(self, mod):
        """Toggle a font modification"""
        if self._textbuffer:
            self._textbuffer.toggle_tag_selected(
                self._textbuffer.tag_table.lookup(RichTextModTag.tag_name(mod)))

    def set_font_mod(self, mod):
        """Sets a font modification"""
        self._apply_tag(RichTextModTag.tag_name(mod))


    def toggle_link(self):
        """Toggles a link tag"""

        tag, start, end = self.get_link()
        if not tag:
            tag = self._textbuffer.tag_table.lookup(
                RichTextLinkTag.tag_name(""))
        self._textbuffer.toggle_tag_selected(tag)


    
    def set_font_family(self, family):
        """Sets the family font of the selection"""
        self._apply_tag(RichTextFamilyTag.tag_name(family))
    
    def set_font_size(self, size):
        """Sets the font size of the selection"""
        self._apply_tag(RichTextSizeTag.tag_name(size))
    
    def set_justify(self, justify):
        """Sets the text justification"""
        self._apply_tag(RichTextJustifyTag.tag_name(justify))

    def set_font_fg_color(self, color):
        """Sets the text foreground color"""
        if self._textbuffer:
            if color:
                self._textbuffer.toggle_tag_selected(
                    self._textbuffer.tag_table.lookup(
                        RichTextFGColorTag.tag_name(color)))
            else:
                self._textbuffer.remove_tag_class_selected(
                    self._textbuffer.tag_table.lookup(
                        RichTextFGColorTag.tag_name("#000000")))

        
    def set_font_bg_color(self, color):
        """Sets the text background color"""
        if self._textbuffer:

            if color:
                self._textbuffer.toggle_tag_selected(
                    self._textbuffer.tag_table.lookup(
                        RichTextBGColorTag.tag_name(color)))
            else:
                self._textbuffer.remove_tag_class_selected(
                    self._textbuffer.tag_table.lookup(
                        RichTextBGColorTag.tag_name("#000000")))

    def toggle_bullet(self, par_type=None):
        """Toggle state of a bullet list"""
        if self._textbuffer:
            self._textbuffer.toggle_bullet_list(par_type)


    def set_font(self, font_name):
        """Font change from choose font widget"""

        if not self._textbuffer:
            return
        
        family, mods, size = parse_font(font_name)

        self._textbuffer.begin_user_action()
        
        # apply family and size tags
        self.set_font_family(family)
        self.set_font_size(size)
        
        # apply modifications
        for mod in mods:
            self.set_font_mod(mod)

        # disable modifications not given
        mod_class = self._textbuffer.tag_table.get_tag_class("mod")
        for tag in mod_class.tags:
            if tag.get_property("name") not in mods:
                self._textbuffer.remove_tag_selected(tag)

        self._textbuffer.end_user_action()
    
    #==================================================================
    # UI Updating from changing font under cursor


    def _on_font_change(self, textbuffer, font):
        """Callback for when font under cursor changes"""

        # forward signal along to listeners
        self.emit("font-change", font)
    
    def get_font(self):
        """Get the font under the cursor"""
        if self._textbuffer:
            return self._textbuffer.get_font()
        else:
            return self._blank_buffer.get_font()


    def set_default_font(self, font):
        """Sets the default font of the textview"""
        try:

            # HACK: fix small font sizes on Mac
            #PIXELS_PER_PANGO_UNIT = 1024
            #native_size = self.get_default_attributes().font.get_size() // PIXELS_PER_PANGO_UNIT
            #set_text_scale(native_size / 10.0)

            f = pango.FontDescription(font)
            f.set_size(int(f.get_size() * get_text_scale()))
            self.modify_font(f)
        except:
            # TODO: think about how to handle this error
            pass

    
    
    #=========================================
    # undo/redo methods
    
    def undo(self):
        """Undo the last action in the RichTextView"""
        if self._textbuffer:
            self._textbuffer.undo()
            self.scroll_mark_onscreen(self._textbuffer.get_insert())
        
    def redo(self):
        """Redo the last action in the RichTextView"""
        if self._textbuffer:
            self._textbuffer.redo()
            self.scroll_mark_onscreen(self._textbuffer.get_insert())



# register new signals
gobject.type_register(RichTextView)
gobject.signal_new("modified", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (bool,))
gobject.signal_new("font-change", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("child-activated", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("visit-url", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str,))




'''
    def drop_pdf(self, data):
        """Drop a PDF into the TextView"""

        if not self._textbuffer:
            return

        # NOTE: requires hardcoded convert
        # TODO: generalize
        
        self._textbuffer.begin_user_action()
        
        try:
            f, imgfile = tempfile.mkstemp(".png", "pdf")
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
                    self.insert_image_from_file(imgfile)
                    os.remove(imgfile)
                    i += 1
                    
            elif os.path.exists(imgfile):
                
                self.insert_image_from_file(imgfile)
                os.remove(imgfile)
        except:
            if os.path.exists(imgfile):
                os.remove(imgfile)

        self._textbuffer.end_user_action()
    '''
