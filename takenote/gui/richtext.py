"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    General rich text editor that saves to HTML
"""



# python imports
import sys, os, tempfile, re

try:
    import gtkspell
except ImportError:
    gtkspell = None


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

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
     RichTextBuffer, \
     RichTextImage, \
     RichTextError

from takenote.gui.richtext_html import HtmlBuffer, HtmlError

# constants
DEFAULT_FONT = "Sans 10"





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
        self.textbuffer = None
        self.buffer_callbacks = []
        
        self.set_buffer(RichTextBuffer(self))
        self.blank_buffer = RichTextBuffer(self)
        self.set_default_font(DEFAULT_FONT)
        
        
        # spell checker
        self._spell_checker = None
        self.enable_spell_check(True)
        
        # signals
        self.textbuffer.connect("modified-changed", self.on_modified_changed)
        self.block_modified = False
        
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.set_property("right-margin", 5)
        self.set_property("left-margin", 5)
        
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
        self.connect("button-press-event", self.on_button_press)
        
        
        #[('GTK_TEXT_BUFFER_CONTENTS', 1, 0), ('UTF8_STRING', 0, 0), ('COMPOUND_TEXT', 0, 0), ('TEXT', 0, 0), ('STRING', 0, 0), ('text/plain;charset=utf-8', 0, 0), ('text/plain;charset=ANSI_X3.4-1968', 0, 0), ('text/plain', 0, 0)]
        
        #self.connect("populate-popup", self.on_popup)
        
        # initialize HTML buffer
        self.html_buffer = HtmlBuffer()
        
        # popup menus
        self.image_menu = RichTextMenu()
        self.image_menu.attach_to_widget(self, lambda w,m:None)

        item = gtk.ImageMenuItem(gtk.STOCK_CUT)
        item.connect("activate", lambda w: self.emit("cut-clipboard"))
        self.image_menu.append(item)
        item.show()
        
        item = gtk.ImageMenuItem(gtk.STOCK_COPY)
        item.connect("activate", lambda w: self.emit("copy-clipboard"))
        self.image_menu.append(item)
        item.show()

        item = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        item.connect("activate", lambda w: self.textbuffer.delete_selection(True, True))
        self.image_menu.append(item)
        item.show()
        

        
        # requires new pygtk
        #self.textbuffer.register_serialize_format(MIME_TAKENOTE, 
        #                                          self.serialize, None)
        #self.textbuffer.register_deserialize_format(MIME_TAKENOTE, 
        #                                            self.deserialize, None)

    def on_modified_changed(self, textbuffer):
        
        # propogate modified signal to listeners of this textview
        if not self.block_modified:
            self.emit("modified", textbuffer.get_modified())
    
    
    def set_buffer(self, textbuffer):
        # tell current buffer we are detached
        if self.textbuffer:
            self.textbuffer.set_textview(None)

            for callback in self.buffer_callbacks:
                self.textbuffer.disconnect(callback)

        
        # change buffer
        if textbuffer:
            gtk.TextView.set_buffer(self, textbuffer)
            
        else:
            gtk.TextView.set_buffer(self, self.blank_buffer)
        self.textbuffer = textbuffer


        # tell new buffer we are attached
        if self.textbuffer:
            self.textbuffer.default_attr = self.get_default_attributes()
            self.textbuffer.set_textview(self)

            self.callbacks = [
                self.textbuffer.connect("font-change",
                                        self.on_font_change),
                self.textbuffer.connect("child-activated",
                                        self.on_child_activated),
                self.textbuffer.connect("child-menu",
                                        self.on_child_popup_menu)
                ]


    def on_button_press(self, widget, event):
        pass #print "click"

    

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
            
            self.textbuffer.insert_at_cursor(selection_data.get_text())
                        
            
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
            out = open(filename, "wb")
            self.html_buffer.set_output(out)
            self.html_buffer.write(self.textbuffer)
            out.close()
        except IOError, e:
            raise RichTextError("Could not save '%s'." % filename, e)
        
        self.textbuffer.set_modified(False)
    
    
    def load(self, filename):
        textbuffer = self.textbuffer
        
        # unhook expensive callbacks
        self.block_modified = True
        textbuffer.undo_stack.suppress()
        textbuffer.block_signals()
        self.set_buffer(None)
        
        # clear buffer        
        textbuffer.clear()
        
        err = None
        try:
            #from rasmus import util
            #util.tic("read")
        
            self.html_buffer.read(textbuffer, open(filename, "r"))
            
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
            self.load_images(path)
            
            ret = True
        
        # rehook up callbacks
        textbuffer.unblock_signals()
        self.textbuffer.undo_stack.resume()
        self.textbuffer.undo_stack.reset()
        self.enable()

        self.block_modified = False        
        self.textbuffer.set_modified(False)

        
        if not ret:
            raise RichTextError("Error loading '%s'." % filename, e)
        
   
        
    
    def load_images(self, path):
        """Load images present in textbuffer"""
        
        for kind, it, param in iter_buffer_contents(self.textbuffer,
                                                    None, None,
                                                    IGNORE_TAGS):
            if kind == "anchor":
                child, widgets = param
                    
                if isinstance(child, RichTextImage):
                    filename = os.path.join(path, child.get_filename())
                    child.set_from_file(filename)
                    child.get_widget().show()

    
    def save_images(self, path):
        """Save images present in text buffer"""
        
        for kind, it, param in iter_buffer_contents(self.textbuffer,
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
        return self.textbuffer.get_modified()
    
        
    def enable(self):
        self.set_sensitive(True)
    
    
    def disable(self):
        
        self.block_modified = True
        self.textbuffer.undo_stack.suppress()
        
        start = self.textbuffer.get_start_iter()
        end = self.textbuffer.get_end_iter()
        self.textbuffer.remove_all_tags(start, end)
        self.textbuffer.delete(start, end)
        self.set_sensitive(False)
        
        self.textbuffer.undo_stack.resume()
        self.textbuffer.undo_stack.reset()
        self.block_modified = False
        self.textbuffer.set_modified(False)
    
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
        self.image_menu.set_child(child)
        
        if isinstance(child, RichTextImage):
            self.image_menu.popup(None, None, None, button, activate_time)
            self.image_menu.show()
            
    def get_image_menu(self):
        return self.image_menu

    #==========================================
    # child events

    def on_child_activated(self, textbuffer, child):
        self.emit("child-activated", child)
        
    
    #===========================================================
    # Actions
        
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer"""
                
        self.textbuffer.insert_image(image, filename)    


    def insert_hr(self):
        self.textbuffer.insert_hr()
        
    
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
    
    def on_font_change(self, textbuffer, mods, justify, family, size):
        self.emit("font-change", mods, justify, family, size)
    
    def get_font(self):
        return self.textbuffer.get_font()

    def set_default_font(self, font):
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
        self.textbuffer.undo()
        
    def redo(self):
        """Redo the last action in the RichTextView"""    
        self.textbuffer.redo()    


gobject.type_register(RichTextView)
gobject.signal_new("modified", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (bool,))
gobject.signal_new("font-change", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, str, str, int))
gobject.signal_new("child-activated", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
#gobject.signal_new("error", RichTextView, gobject.SIGNAL_RUN_LAST, 
#    gobject.TYPE_NONE, (str, object,))

