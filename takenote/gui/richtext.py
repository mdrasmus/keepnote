"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    General rich text editor that saves to HTML
"""



# python imports
import sys, os, tempfile, re
import urllib2

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# try to import spell check
try:
    import gtkspell
except ImportError:
    gtkspell = None


# takenote imports
import takenote

from takenote.gui.textbuffer_tools import \
     iter_buffer_contents, \
     buffer_contents_iter_to_offset, \
     normalize_tags, \
     insert_buffer_contents, \
     buffer_contents_apply_tags

from takenote.gui.richtextbuffer import \
     IGNORE_TAGS, \
     parse_utf, \
     add_child_to_buffer, \
     RichTextBuffer, \
     RichTextImage, \
     RichTextError

from takenote.gui.richtext_html import HtmlBuffer, HtmlError


# constants
DEFAULT_FONT = "Sans 10"
TEXTVIEW_MARGIN = 5

# mime types
MIME_TAKENOTE = "application/x-takenote"
MIME_IMAGES = ["image/png",
               "image/bmp",
               "image/jpeg",
               "image/xpm"]
MIME_TEXT = ["text/plain",
             "text/plain;charset=utf-8",
             "text/plain;charset=UTF-8",
             "UTF8_STRING",
             "STRING",
             "COMPOUND_TEXT",
             "TEXT"]



#=============================================================================


class RichTextMenu (gtk.Menu):
    """A popup menu for child widgets in a RichTextView"""
    def __inti__(self):
        gkt.Menu.__init__(self)
        self._child = None

    def set_child(self, child):
        self._child = child

    def get_child(self):
        return self._child


class RichTextView (gtk.TextView):
    """A RichText editor widget"""

    def __init__(self):
        gtk.TextView.__init__(self, None)
        self._textbuffer = None
        self._buffer_callbacks = []
        self._clipboard_contents = None
        
        self.set_buffer(RichTextBuffer(self))
        self._blank_buffer = RichTextBuffer(self)
        self.set_default_font(DEFAULT_FONT)
        
        
        # spell checker
        self._spell_checker = None
        self.enable_spell_check(True)
        
        # signals
        self._textbuffer.connect("modified-changed", self.on_modified_changed)
        self._block_modified = False
        
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.set_property("right-margin", TEXTVIEW_MARGIN)
        self.set_property("left-margin", TEXTVIEW_MARGIN)
        

        # drag and drop
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("drag-motion", self.on_drag_motion)
        self.drag_dest_add_image_targets()

        # clipboard
        self.connect("copy-clipboard", lambda w: self.on_copy())
        self.connect("cut-clipboard", lambda w: self.on_cut())
        self.connect("paste-clipboard", lambda w: self.on_paste())

        #self.connect("button-press-event", self.on_button_press)
        
        
        #[('GTK_TEXT_BUFFER_CONTENTS', 1, 0), ('UTF8_STRING', 0, 0), ('COMPOUND_TEXT', 0, 0), ('TEXT', 0, 0), ('STRING', 0, 0), ('text/plain;charset=utf-8', 0, 0), ('text/plain;charset=ANSI_X3.4-1968', 0, 0), ('text/plain', 0, 0)]        
        #self.connect("populate-popup", self.on_popup)
        
        # initialize HTML buffer
        self._html_buffer = HtmlBuffer()

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
        item.connect("activate", lambda w: self._textbuffer.delete_selection(True, True))
        self._image_menu.append(item)
        item.show()

    
    
    def set_buffer(self, textbuffer):
        """Attach this textview to a RichTextBuffer"""
        
        # tell current buffer we are detached
        if self._textbuffer:
            self._textbuffer.set_textview(None)

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
            self._textbuffer.default_attr = self.get_default_attributes()
            self._textbuffer.set_textview(self)

            self._buffer_callbacks = [
                self._textbuffer.connect("font-change",
                                        self.on_font_change),
                self._textbuffer.connect("child-activated",
                                        self.on_child_activated),
                self._textbuffer.connect("child-menu",
                                        self.on_child_popup_menu)
                ]


    #def on_button_press(self, widget, event):
    #    pass #print "click"

    

    #=======================================================
    # Drag and drop

    def on_drag_motion(self, textview, drag_context, x, y, timestamp):
        """Callback for when dragging over textview"""
        
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

        elif "text/html" in drag_context.targets:
            textview.drag_dest_set_target_list([("text/html", 0, 0)])
            
        else:
            textview.drag_dest_set_target_list([("text/plain", 0, 0)])
            
    
    
    def on_drag_data_received(self, widget, drag_context, x, y,
                              selection_data, info, eventtime):
        """Callback for when drop event is received"""
        
        img_target = self.drag_dest_find_target(drag_context, 
            [("image/png", 0, 0) ,
             ("image/bmp", 0, 0) ,
             ("image/jpeg", 0, 0),
             ("image/xpm", 0, 0)])
             
        if img_target not in (None, "NONE"):
            # process image drop
            pixbuf = selection_data.get_pixbuf()
            
            if pixbuf != None:
                image = RichTextImage()
                image.set_from_pixbuf(pixbuf)
        
                self.insert_image(image)
            
                drag_context.finish(True, True, eventtime)
                self.stop_emission("drag-data-received")
                
                
        elif self.drag_dest_find_target(drag_context, 
            [("application/pdf", 0, 0)]) not in (None, "NONE"):
            # process pdf drop
            
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
                    self.insert_image_from_file(imgfile)
                    os.remove(imgfile)
                    i += 1
                    
            elif os.path.exists(imgfile):
                
                self.insert_image_from_file(imgfile)
                os.remove(imgfile)
            
            drag_context.finish(True, True, eventtime)
            self.stop_emission("drag-data-received")

        elif self.drag_dest_find_target(drag_context, 
            [("text/html", 0, 0)]) not in (None, "NONE"):
            # process html drop

            html = parse_utf(selection_data.data)
            self.insert_html(html)
            
        
        elif self.drag_dest_find_target(drag_context, 
            [("text/plain", 0, 0)]) not in (None, "NONE"):
            # process text drop

            self._textbuffer.begin_user_action()
            self._textbuffer.insert_at_cursor(selection_data.get_text())
            self._textbuffer.end_user_action()
            

        
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
        self.stop_emission('copy-clipboard')
        
        self.copy_clipboard(clipboard)

    
    def on_cut(self):
        """Callback for cut action"""    
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        self.stop_emission('cut-clipboard')
        
        self.cut_clipboard(clipboard, self.get_editable())

    
    def on_paste(self):
        """Callback for paste action"""    
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        self.stop_emission('paste-clipboard')
        
        self.paste_clipboard(clipboard, None, self.get_editable())
        

    def copy_clipboard(self, clipboard):
        """Callback for copy event"""
                
        
        sel = self._textbuffer.get_selection_bounds()

        # do nothing if nothing is selected
        if sel is None:
            return
        
        start, end = sel
        contents = list(iter_buffer_contents(self._textbuffer, start, end))

        
        if len(contents) == 1 and \
           contents[0][0] == "anchor" and \
           isinstance(contents[0][2][0], RichTextImage):
            # copy image
            targets = [(x, 0, -3) for x in MIME_IMAGES]
            
            clipboard.set_with_data(targets, self.get_selection_data, 
                                    self.clear_selection_data,
                                    (contents[0][2][0], ""))

        else:
            # copy text
            targets = [(MIME_TAKENOTE, gtk.TARGET_SAME_APP, -3),
                       ("text/html", 0, -3)] + \
                      [(x, 0, -3) for x in MIME_TEXT]
            
            text = start.get_text(end)
            clipboard.set_with_data(targets, self.get_selection_data, 
                                    self.clear_selection_data,
                                    (contents, text))


    def cut_clipboard(self, clipboard, default_editable):
        """Callback for cut event"""
        
        self.copy_clipboard(clipboard)
        self._textbuffer.delete_selection(False, default_editable)

    
    def paste_clipboard(self, clipboard, override_location, default_editable):
        """Callback for paste event"""
        
        targets = set(clipboard.wait_for_targets())
        
        if targets is None:
            # do nothing
            return
            
        
        if MIME_TAKENOTE in targets:
            clipboard.request_contents(MIME_TAKENOTE, self.do_paste_object)
        elif "text/html" in targets:
            clipboard.request_contents("text/html", self.do_paste_html)
        else:

            # test image formats
            for mime_image in MIME_IMAGES:
                if mime_image in targets:
                    clipboard.request_contents(mime_image,
                                               self.do_paste_image)
                    break
            else:
                # request text
                clipboard.request_text(self.do_paste_text)
        
    
    def do_paste_text(self, clipboard, text, data):
        """Paste text into buffer"""
        self._textbuffer.begin_user_action()
        self._textbuffer.delete_selection(False, True)
        self._textbuffer.insert_at_cursor(text)
        self._textbuffer.end_user_action()

    def do_paste_html(self, clipboard, selection_data, data):
        """Paste HTML into buffer"""
        
        html = parse_utf(selection_data.data)        
        self._textbuffer.begin_user_action()
        self._textbuffer.delete_selection(False, True)
        self.insert_html(html)
        self._textbuffer.end_user_action()
        
        
    
    def do_paste_image(self, clipboard, selection_data, data):
        """Paste image into buffer"""
        
        pixbuf = selection_data.get_pixbuf()
        image = RichTextImage()
        image.set_from_pixbuf(pixbuf)
        
        self._textbuffer.insert_image(image)

    
    def do_paste_object(self, clipboard, selection_data, data):
        """Paste a program-specific object into buffer"""
        
        if self._clipboard_contents is None:
            # do nothing
            return
        
        self._textbuffer.begin_user_action()
        it = self._textbuffer.get_iter_at_mark(self._textbuffer.get_insert())
        insert_buffer_contents(self._textbuffer, it,
                               self._clipboard_contents,
                               add_child=add_child_to_buffer)
        self._textbuffer.end_user_action()
    
    
    def get_selection_data(self, clipboard, selection_data, info, data):
        """Callback for when Clipboard needs selection data"""

        contents, text = data
        
        self._clipboard_contents = contents
        
        
        if MIME_TAKENOTE in selection_data.target:
            # set rich text
            selection_data.set(MIME_TAKENOTE, 8, "<takenote>")
            
        elif "text/html" in selection_data.target:
            # set html
            stream = StringIO.StringIO(data)
            self._html_buffer.set_output(stream)
            self._html_buffer.write(contents, partial=True)
            selection_data.set("text/html", 8, stream.getvalue())

        elif len([x for x in MIME_IMAGES
                  if x in selection_data.target]) > 0:
            # set image
            selection_data.set_pixbuf(contents.get_original_pixbuf())
            
        else:
            # set plain text
            selection_data.set_text(text)

    
    def clear_selection_data(self, clipboard, data):
        """Callback for when Clipboard contents are reset"""
        self._clipboard_contents = None


    
    #==================================================================
    # File I/O
    
    def save(self, filename):
        """Save buffer contents to file"""
        
        path = os.path.dirname(filename)
        self._save_images(path)
        
        try:
            buffer_contents = iter_buffer_contents(self._textbuffer,
                                                   None,
                                                   None,
                                                   IGNORE_TAGS)
            
            out = open(filename, "wb")
            self._html_buffer.set_output(out)
            self._html_buffer.write(buffer_contents)
            out.close()
        except IOError, e:
            raise RichTextError("Could not save '%s'." % filename, e)
        
        self._textbuffer.set_modified(False)
    
    
    def load(self, filename):
        """Load buffer with data from file"""
        
        textbuffer = self._textbuffer
        
        # unhook expensive callbacks
        self._block_modified = True
        textbuffer.undo_stack.suppress()
        textbuffer.block_signals()
        self.set_buffer(None)
        
        # clear buffer        
        textbuffer.clear()
        
        err = None
        try:
            #from rasmus import util
            #util.tic("read")

            # NOTE: buffer_contents is a generator
            buffer_contents = self._html_buffer.read(open(filename, "r"))
            insert_buffer_contents(textbuffer,
                                   textbuffer.get_start_iter(),
                                   buffer_contents,
                                   add_child_to_buffer,
                                   lookup_tag=lambda name:
                                       textbuffer.lookup_tag(name))

            # put cursor at begining
            textbuffer.place_cursor(textbuffer.get_start_iter())
            
            #util.toc()
            
        except (HtmlError, IOError), e:
            err = e
            
            # TODO: turn into function
            textbuffer.clear()
            self.set_buffer(textbuffer)
            
            ret = False
        else:
            self.set_buffer(textbuffer)
            textbuffer.add_deferred_anchors()
        
            path = os.path.dirname(filename)
            self._load_images(path)
            
            ret = True
        
        # rehook up callbacks
        textbuffer.unblock_signals()
        self._textbuffer.undo_stack.resume()
        self._textbuffer.undo_stack.reset()
        self.enable()

        self._block_modified = False        
        self._textbuffer.set_modified(False)

        
        if not ret:
            raise RichTextError("Error loading '%s'." % filename, e)
        
   
        
    
    def _load_images(self, path):
        """Load images present in textbuffer"""
        
        for kind, it, param in iter_buffer_contents(self._textbuffer,
                                                    None, None,
                                                    IGNORE_TAGS):
            if kind == "anchor":
                child, widgets = param
                    
                if isinstance(child, RichTextImage):
                    filename = child.get_filename()

                    if not filename.startswith("http:") and \
                       not filename.startswith("/"):
                        filename = os.path.join(path, filename)
                        
                    child.set_from_file(filename)
                    child.get_widget().show()

    
    def _save_images(self, path):
        """Save images present in text buffer"""
        
        for kind, it, param in iter_buffer_contents(self._textbuffer,
                                                    None, None,
                                                    IGNORE_TAGS):
            if kind == "anchor":
                child, widgets = param
                    
                if isinstance(child, RichTextImage):
                    filename = os.path.join(path, child.get_filename())
                    if child.save_needed():
                        child.write(filename)
                    

    #=============================================
    # State
    
    def is_modified(self):
        """Returns True if buffer is modified"""
        return self._textbuffer.get_modified()

    
    def on_modified_changed(self, textbuffer):
        """Callback for when buffer is modified"""
        
        # propogate modified signal to listeners of this textview
        if not self._block_modified:
            self.emit("modified", textbuffer.get_modified())

        
    def enable(self):
        self.set_sensitive(True)
    
    
    def disable(self):
        
        self._block_modified = True
        self._textbuffer.undo_stack.suppress()
        
        start = self._textbuffer.get_start_iter()
        end = self._textbuffer.get_end_iter()
        self._textbuffer.remove_all_tags(start, end)
        self._textbuffer.delete(start, end)
        self.set_sensitive(False)
        
        self._textbuffer.undo_stack.resume()
        self._textbuffer.undo_stack.reset()
        self._block_modified = False
        self._textbuffer.set_modified(False)
    
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

    def on_child_popup_menu(self, textbuffer, child, button, activate_time):
        """Callback for when child menu should appear"""
        self._image_menu.set_child(child)
        
        if isinstance(child, RichTextImage):
            self._image_menu.popup(None, None, None, button, activate_time)
            self._image_menu.show()
            
    def get_image_menu(self):
        """Returns the image popup menu"""
        return self._image_menu

    #==========================================
    # child events

    def on_child_activated(self, textbuffer, child):
        """Callback for when child has been activated"""
        self.emit("child-activated", child)
        
    
    #===========================================================
    # Actions
        
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer"""
                
        self._textbuffer.insert_image(image, filename)    

    def insert_image_from_file(self, imgfile, filename="image.png"):
        """Inserts an image from a file"""
        
        pixbuf = gdk.pixbuf_new_from_file(imgfile)
        img = RichTextImage()
        img.set_from_pixbuf(pixbuf)
        self.insert_image(img, filename)

    def insert_hr(self):
        """Inserts a horizontal rule"""
        self._textbuffer.insert_hr()
        
        
    def insert_html(self, html):
        """Insert HTML content into Buffer"""
        
        contents = list(self._html_buffer.read([html],
                                               partial=True,
                                               ignore_errors=True))

        # scan contents
        for kind, pos, param in contents:
            
            # download and images included in html
            if kind == "anchor" and isinstance(param[0], RichTextImage):
                img = param[0]
                if img.get_filename().startswith("http:") or \
                   img.get_filename().startswith("file:"):
                    img.set_from_url(img.get_filename(), "image.png")
        
        # add to buffer
        self._textbuffer.begin_user_action()
        insert_buffer_contents(self._textbuffer,
                               self._textbuffer.get_iter_at_mark(
                                   self._textbuffer.get_insert()),
                               contents,
                               add_child=add_child_to_buffer,
                               lookup_tag=lambda name:
                                   self._textbuffer.lookup_tag(name))
        self._textbuffer.end_user_action()




    #==========================================================
    # Find/Replace
    
    def forward_search(self, it, text, case_sensitive):
        """Finds next occurrence of 'text' searching forwards"""
        
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
        """Finds next occurrence of 'text' searching backwards"""
        
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
                case_sensitive=False, forward=True, next=True):
        """Replaces next occurrence of 'text' with 'replace_text'"""
        
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
        found = False
        
        self._textbuffer.begin_user_action()
        while self.replace(text, replace_text, case_sensitive, forward, False) != -1:
            found = True
        self._textbuffer.end_user_action()
        
        return found

    #===========================================================
    # Spell check
    
    def can_spell_check(self):
        return gtkspell is not None
    
    def enable_spell_check(self, enabled=True):
        if not self.can_spell_check():
            return           
        
        if enabled:
            if self._spell_checker is None:
                self._spell_checker = gtkspell.Spell(self)
        else:
            if self._spell_checker is not None:
                self._spell_checker.detach()
                self._spell_checker = None

    def is_spell_check_enabled(self):
        return self._spell_checker != None
        
    #===========================================================
    # Callbacks from UI to change font 

    def on_bold(self):
        """Toggle bold of selection"""
        self._textbuffer.toggle_tag_selected(self._textbuffer.bold_tag)
        
    def on_italic(self):
        """Toggle italics of selection"""
        self._textbuffer.toggle_tag_selected(self._textbuffer.italic_tag)
    
    def on_underline(self):
        """Toggle underline of selection"""
        self._textbuffer.toggle_tag_selected(self._textbuffer.underline_tag)
        
    def on_no_wrap(self):
        """Toggle no text wrap of selection"""
        self._textbuffer.toggle_tag_selected(self._textbuffer.no_wrap_tag)

    
    def on_font_set(self, widget):
        """Font change from choose font widget"""
        family, mods, size = self._textbuffer.parse_font(widget.get_font_name())
        
        # apply family tag
        self._textbuffer.apply_tag_selected(self._textbuffer.lookup_family_tag(family))
        
        # apply size
        self._textbuffer.apply_tag_selected(self._textbuffer.lookup_size_tag(size))
        
        # apply mods
        for mod in mods:
            self._textbuffer.apply_tag_selected(self._textbuffer.tag_table.lookup(mod))
        
        # disable mods not given
        for mod in ["Bold", "Italic", "Underline"]:
            if mod not in mods:
                self._textbuffer.remove_tag_selected(self._textbuffer.tag_table.lookup(mod))
    
    def on_font_family_set(self, family):
        """Sets the family font of the selection"""
        self._textbuffer.apply_tag_selected(self._textbuffer.lookup_family_tag(family))
    
    def on_font_family_toggle(self, family):
        """Toggles the family font of the selection"""
        self._textbuffer.toggle_tag_selected(self._textbuffer.lookup_family_tag(family))
    
    def on_font_size_set(self, size):
        """Sets the font size of the selection"""
        self._textbuffer.apply_tag_selected(self._textbuffer.lookup_size_tag(size))
    
    def on_left_justify(self):
        """Sets the justification of the selection to be left"""
        self._textbuffer.apply_tag_selected(self._textbuffer.left_tag)
        
    def on_center_justify(self):
        """Sets the justification of the selection to be center"""
        self._textbuffer.apply_tag_selected(self._textbuffer.center_tag)
    
    def on_right_justify(self):
        """Sets the justification of the selection to be right"""
        self._textbuffer.apply_tag_selected(self._textbuffer.right_tag)
    
    def on_fill_justify(self):
        """Sets the justification of the selection to be justify"""
        self._textbuffer.apply_tag_selected(self._textbuffer.fill_tag)

    
    #==================================================================
    # UI Updating from chaning font under cursor
    
    def on_font_change(self, textbuffer, mods, justify, family, size):
        """Callback for when font under cursor changes"""
        self.emit("font-change", mods, justify, family, size)
    
    def get_font(self):
        """Get the font under the cursor"""
        return self._textbuffer.get_font()

    def set_default_font(self, font):
        """Sets the default font of the textview"""
        try:
            f = pango.FontDescription(font)
            self.modify_font(f)
        except:
            # TODO: think about how to handle this error
            pass

    
    
    #=========================================
    # undo/redo methods
    
    def undo(self):
        """Undo the last action in the RichTextView"""
        self._textbuffer.undo()
        
    def redo(self):
        """Redo the last action in the RichTextView"""    
        self._textbuffer.redo()    



# register new signals
gobject.type_register(RichTextView)
gobject.signal_new("modified", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (bool,))
gobject.signal_new("font-change", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, str, str, int))
gobject.signal_new("child-activated", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))


