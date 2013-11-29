"""

    KeepNote
    Editor widget in main window

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
import os
import re

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# keepnote imports
import keepnote
from keepnote import \
    KeepNoteError, is_url, unicode_gtk
from keepnote.notebook import \
    NoteBookError, \
    get_node_url, \
    parse_node_url, \
    is_node_url
from keepnote import notebook as notebooklib
from keepnote.gui import dialog_image_new
from keepnote.gui.richtext import \
    RichTextView, RichTextBuffer, \
    RichTextIO, RichTextError, RichTextImage
from keepnote.gui.richtext.richtext_tags import RichTextLinkTag
from keepnote.gui.icons import lookup_icon_filename
from keepnote.gui.font_selector import FontSelector
from keepnote.gui.colortool import FgColorTool, BgColorTool
from keepnote.gui.linkcomplete import LinkPickerPopup
from keepnote.gui.link_editor import LinkEditor
from keepnote.gui.editor import KeepNoteEditor
from keepnote.gui import \
    CONTEXT_MENU_ACCEL_PATH, \
    DEFAULT_FONT, \
    DEFAULT_COLORS, \
    FileChooserDialog, \
    get_resource_pixbuf, \
    Action, \
    ToggleAction, \
    add_actions, \
    update_file_preview, \
    dialog_find, \
    dialog_image_resize


_ = keepnote.translate


def is_relative_file(filename):
    """Returns True if filename is relative"""
    return (not re.match("[^:/]+://", filename) and
            not os.path.isabs(filename))


def is_local_file(filename):
    return filename and ("/" not in filename) and ("\\" not in filename)


class NodeIO (RichTextIO):
    """Read/Writes the contents of a RichTextBuffer to disk"""

    def __init__(self):
        RichTextIO.__init__(self)
        self._node = None
        self._image_files = set()
        self._saved_image_files = set()

    def set_node(self, node):
        self._node = node

    def save(self, textbuffer, filename, title=None, stream=None):
        """Save buffer contents to file"""
        RichTextIO.save(self, textbuffer, filename, title, stream=stream)

    def load(self, textview, textbuffer, filename, stream=None):
        RichTextIO.load(self, textview, textbuffer, filename, stream=stream)

    def _load_images(self, textbuffer, html_filename):
        """Load images present in textbuffer"""
        self._image_files.clear()
        RichTextIO._load_images(self, textbuffer, html_filename)

    def _save_images(self, textbuffer, html_filename):
        """Save images present in text buffer"""
        # reset saved image set
        self._saved_image_files.clear()

        # don't allow the html file to be deleted
        if html_filename:
            self._saved_image_files.add(os.path.basename(html_filename))

        RichTextIO._save_images(self, textbuffer, html_filename)

        # delete images not part of the saved set
        self._delete_images(html_filename,
                            self._image_files - self._saved_image_files)
        self._image_files = set(self._saved_image_files)

    def _delete_images(self, html_filename, image_files):
        for image_file in image_files:
            # only delete an image file if it is local
            if is_local_file(image_file):
                try:
                    self._node.delete_file(image_file)
                except:
                    keepnote.log_error()
                    pass

    def _load_image(self, textbuffer, image, html_filename):
        # TODO: generalize url recognition
        filename = image.get_filename()
        if filename.startswith("http:/") or filename.startswith("file:/"):
            image.set_from_url(filename)
        elif is_relative_file(filename):
            try:
                infile = self._node.open_file(filename, mode="r")
                image.set_from_stream(infile)
                infile.close()
            except:
                image.set_no_image()
        else:
            image.set_from_file(filename)

        # record loaded images
        self._image_files.add(image.get_filename())

    def _save_image(self, textbuffer, image, html_filename):
        if image.save_needed():
            out = self._node.open_file(image.get_filename(), mode="w")
            image.write_stream(out, image.get_filename())
            out.close()

        # mark image as saved
        self._saved_image_files.add(image.get_filename())


class RichTextEditor (KeepNoteEditor):

    def __init__(self, app):
        KeepNoteEditor.__init__(self, app)
        self._app = app
        self._notebook = None

        self._link_picker = None
        self._maxlinks = 10  # maximum number of links to show in link picker

        # state
        self._page = None                  # current NoteBookPage
        self._page_scrolls = {}            # remember scroll in each page
        self._page_cursors = {}
        self._textview_io = NodeIO()

        # editor
        self.connect("make-link", self._on_make_link)

        # textview and its callbacks
        self._textview = RichTextView(RichTextBuffer(
            self._app.get_richtext_tag_table()))  # textview
        self._textview.disable()
        self._textview.connect("font-change", self._on_font_callback)
        self._textview.connect("modified", self._on_modified_callback)
        self._textview.connect("child-activated", self._on_child_activated)
        self._textview.connect("visit-url", self._on_visit_url)
        self._textview.get_buffer().connect("ending-user-action",
                                            self._on_text_changed)
        self._textview.connect("key-press-event", self._on_key_press_event)

        # scrollbars
        self._sw = gtk.ScrolledWindow()
        self._sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self._sw.set_shadow_type(gtk.SHADOW_IN)
        self._sw.add(self._textview)
        self.pack_start(self._sw)

        # link editor
        self._link_editor = LinkEditor()
        self._link_editor.set_textview(self._textview)
        self._link_editor.set_search_nodes(self._search_nodes)
        self.connect("font-change", self._link_editor.on_font_change)
        self.pack_start(self._link_editor, False, True, 0)

        self.make_image_menu(self._textview.get_image_menu())

        # menus
        self.editor_menus = EditorMenus(self._app, self)
        self.connect("font-change", self.editor_menus.on_font_change)

        # find dialog
        self.find_dialog = dialog_find.KeepNoteFindDialog(self)

        self.show_all()

    def set_notebook(self, notebook):
        """Set notebook for editor"""
        # set new notebook
        self._notebook = notebook

        if self._notebook:
            self.load_notebook_preferences()
        else:
            # no new notebook, clear the view
            self.clear_view()

    def get_notebook(self):
        """Returns notebook"""
        return self._notebook

    def load_preferences(self, app_pref, first_open=False):
        """Load application preferences"""
        self.editor_menus.enable_spell_check(
            app_pref.get("editors", "general", "spell_check",
                         default=True))

        try:
            format = app_pref.get("editors", "general", "quote_format")
            self._textview.set_quote_format(format)
        except:
            pass

        self.load_notebook_preferences()

    def save_preferences(self, app_pref):
        """Save application preferences"""
        # record state in preferences
        app_pref.set("editors", "general", "spell_check",
                     self._textview.is_spell_check_enabled())
        app_pref.set("editors", "general", "quote_format",
                     self._textview.get_quote_format())

    def load_notebook_preferences(self):
        """Load notebook-specific preferences"""
        if self._notebook:
            # read default font
            self._textview.set_default_font(
                self._notebook.pref.get("default_font",
                                        default=DEFAULT_FONT))

    def is_focus(self):
        """Return True if text editor has focus"""
        return self._textview.is_focus()

    def grab_focus(self):
        """Pass focus to textview"""
        self._textview.grab_focus()

    def clear_view(self):
        """Clear editor view"""
        self._page = None
        self._textview.disable()

    def undo(self):
        """Undo the last action in the viewer"""
        self._textview.undo()

    def redo(self):
        """Redo the last action in the viewer"""
        self._textview.redo()

    def view_nodes(self, nodes):
        """View a page in the editor"""

        # editor cannot view multiple nodes at once
        # if asked to, it will view none
        if len(nodes) > 1:
            nodes = []

        # save current page before changing nodes
        self.save()
        self._save_cursor()

        pages = [node for node in nodes
                 if node.get_attr("content_type") ==
                 notebooklib.CONTENT_TYPE_PAGE]

        if len(pages) == 0:
            self.clear_view()

        else:
            page = pages[0]
            self._page = page
            self._textview.enable()

            try:
                self._textview.set_current_url(page.get_url(),
                                               title=page.get_title())
                self._textview_io.set_node(self._page)
                self._textview_io.load(
                    self._textview,
                    self._textview.get_buffer(),
                    self._page.get_page_file(),
                    stream=self._page.open_file(
                        self._page.get_page_file(), "r", "utf-8"))
                self._load_cursor()

            except RichTextError, e:
                self.clear_view()
                self.emit("error", e.msg, e)
            except Exception, e:
                self.clear_view()
                self.emit("error", "Unknown error", e)

        if len(pages) > 0:
            self.emit("view-node", pages[0])

    def _save_cursor(self):
        if self._page is not None:
            it = self._textview.get_buffer().get_insert_iter()
            self._page_cursors[self._page] = it.get_offset()

            x, y = self._textview.window_to_buffer_coords(
                gtk.TEXT_WINDOW_TEXT, 0, 0)
            it = self._textview.get_iter_at_location(x, y)
            self._page_scrolls[self._page] = it.get_offset()

    def _load_cursor(self):

        # place cursor in last location
        if self._page in self._page_cursors:
            offset = self._page_cursors[self._page]
            it = self._textview.get_buffer().get_iter_at_offset(offset)
            self._textview.get_buffer().place_cursor(it)

        # place scroll in last position
        if self._page in self._page_scrolls:
            offset = self._page_scrolls[self._page]
            buf = self._textview.get_buffer()
            it = buf.get_iter_at_offset(offset)
            mark = buf.create_mark(None, it, True)
            self._textview.scroll_to_mark(
                mark, 0.49, use_align=True, xalign=0.0)
            buf.delete_mark(mark)

    def save(self):
        """Save the loaded page"""

        if self._page is not None and \
           self._page.is_valid() and \
           self._textview.is_modified():

            try:
                # save text data
                self._textview_io.save(
                    self._textview.get_buffer(),
                    self._page.get_page_file(),
                    self._page.get_title(),
                    stream=self._page.open_file(
                        self._page.get_page_file(), "w", "utf-8"))

                # save meta data
                self._page.set_attr_timestamp("modified_time")
                self._page.save()

            except RichTextError, e:
                self.emit("error", e.msg, e)

            except NoteBookError, e:
                self.emit("error", e.msg, e)

    def save_needed(self):
        """Returns True if textview is modified"""
        return self._textview.is_modified()

    def add_ui(self, window):
        self._textview.set_accel_group(window.get_accel_group())
        self._textview.set_accel_path(CONTEXT_MENU_ACCEL_PATH)
        self._textview.get_image_menu().set_accel_group(
            window.get_accel_group())

        self.editor_menus.add_ui(window)

    def remove_ui(self, window):
        self.editor_menus.remove_ui(window)

    #===========================================
    # callbacks for textview

    def _on_font_callback(self, textview, font):
        """Callback for textview font changed"""
        self.emit("font-change", font)
        self._check_link(False)

    def _on_modified_callback(self, textview, modified):
        """Callback for textview modification"""
        self.emit("modified", self._page, modified)

        # make notebook node modified
        if modified:
            self._page.mark_modified()
            self._page.notify_change(False)

    def _on_child_activated(self, textview, child):
        """Callback for activation of textview child widget"""
        self.emit("child-activated", textview, child)

    def _on_text_changed(self, textview):
        """Callback for textview text change"""
        self._check_link()

    def _on_key_press_event(self, textview, event):
        """Callback for keypress in textview"""

        # decide if keypress should be forwarded to link picker
        if (self._link_picker and self._link_picker.shown() and
            (event.keyval == gtk.keysyms.Down or
             event.keyval == gtk.keysyms.Up or
             event.keyval == gtk.keysyms.Return or
             event.keyval == gtk.keysyms.Escape)):

            return self._link_picker.on_key_press_event(textview, event)

    def _on_visit_url(self, textview, url):
        """Callback for textview visiting a URL"""

        if is_node_url(url):
            host, nodeid = parse_node_url(url)
            node = self._notebook.get_node_by_id(nodeid)
            if node:
                self.emit("visit-node", node)

        else:
            try:
                self._app.open_webpage(url)
            except KeepNoteError, e:
                self.emit("error", e.msg, e)

    def _on_make_link(self, editor):
        """Callback from editor to make a link"""
        self._link_editor.edit()

    #=====================================
    # callback for link editor

    def _search_nodes(self, text):
        """Return nodes with titles containing 'text'"""

        # TODO: make proper interface
        nodes = [(nodeid, title)
                 for nodeid, title in self._notebook.search_node_titles(text)]
        return nodes

    #======================================
    # link auto-complete

    def _check_link(self, popup=True):
        """Check whether complete should be shown for link under cursor"""
        # get link
        tag, start, end = self._textview.get_link()

        if tag is not None and popup:
            # perform node search
            text = start.get_text(end)
            results = []

            # TODO: clean up icon handling.
            for nodeid, title in self._notebook.search_node_titles(text)[
                    :self._maxlinks]:
                icon = self._notebook.get_attr_by_id(nodeid, "icon")
                if icon is None:
                    icon = "note.png"
                icon = lookup_icon_filename(self._notebook, icon)
                if icon is None:
                    icon = lookup_icon_filename(self._notebook, "note.png")

                pb = keepnote.gui.get_pixbuf(icon)

                #if node is not None:
                results.append((get_node_url(nodeid), title, pb))

            # offer url match
            if is_url(text):
                results = [(text, text,
                            get_resource_pixbuf(u"node_icons",
                                                u"web.png"))] + results

            # ensure link picker is initialized
            if self._link_picker is None:
                self._link_picker = LinkPickerPopup(self._textview)
                self._link_picker.connect("pick-link", self._on_pick_link)

            # set results
            self._link_picker.set_links(results)

            # move picker to correct location
            if len(results) > 0:
                rect = self._textview.get_iter_location(start)
                x, y = self._textview.buffer_to_window_coords(
                    gtk.TEXT_WINDOW_WIDGET, rect.x, rect.y)
                rect = self._textview.get_iter_location(end)
                _, y = self._textview.buffer_to_window_coords(
                    gtk.TEXT_WINDOW_WIDGET, rect.x, rect.y)

                self._link_picker.move_on_parent(x, y + rect.height, y)

        elif self._link_picker:
            self._link_picker.set_links([])

    def _on_pick_link(self, widget, title, url):
        """Callback for when link autocomplete has choosen a link"""

        # get current link
        tag, start, end = self._textview.get_link()

        # make new link tag
        tagname = RichTextLinkTag.tag_name(url)
        tag = self._textview.get_buffer().tag_table.lookup(tagname)

        # remember the start iter
        offset = start.get_offset()
        self._textview.get_buffer().delete(start, end)

        # replace link text with node title
        it = self._textview.get_buffer().get_iter_at_offset(offset)
        self._textview.get_buffer().place_cursor(it)
        self._textview.get_buffer().insert_at_cursor(title)

        # get new start and end iters
        end = self._textview.get_buffer().get_insert_iter()
        start = self._textview.get_buffer().get_iter_at_offset(offset)

        # set link tag
        self._textview.set_link(url, start, end)

        # exit link mode
        self._textview.get_buffer().font_handler.clear_current_tag_class(tag)

    #==================================================
    # Image/screenshot actions

    def on_screenshot(self):
        """Take and insert a screen shot image"""
        # do nothing if no page is selected
        if self._page is None:
            return

        imgfile = ""

        # Minimize window
        self.emit("window-request", "minimize")

        try:
            imgfile = self._app.take_screenshot("keepnote")
            self.emit("window-request", "restore")

            # insert image
            self.insert_image(imgfile, "screenshot.png")

        except Exception, e:
            # catch exceptions for screenshot program
            self.emit("window-request", "restore")
            self.emit("error",
                      _("The screenshot program encountered an error:\n %s")
                      % str(e), e)

        # remove temp file
        try:
            if os.path.exists(imgfile):
                os.remove(imgfile)
        except OSError, e:
            self.emit("error",
                      _("%s was unable to remove temp file for screenshot") %
                      keepnote.PROGRAM_NAME)

    def on_insert_hr(self):
        """Insert horizontal rule into editor"""
        if self._page is None:
            return
        self._textview.insert_hr()

    def on_insert_image(self):
        """Displays the Insert Image Dialog"""
        if self._page is None:
            return

        dialog = FileChooserDialog(
            _("Insert Image From File"), self.get_toplevel(),
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Insert"), gtk.RESPONSE_OK),
            app=self._app,
            persistent_path="insert_image_path")

        # add image filters
        filter = gtk.FileFilter()
        filter.set_name("Images")
        filter.add_mime_type("image/png")
        filter.add_mime_type("image/jpeg")
        filter.add_mime_type("image/gif")
        filter.add_pattern("*.png")
        filter.add_pattern("*.jpg")
        filter.add_pattern("*.gif")
        filter.add_pattern("*.tif")
        filter.add_pattern("*.xpm")
        dialog.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        dialog.add_filter(filter)

        # setup preview
        preview = gtk.Image()
        dialog.set_preview_widget(preview)
        dialog.connect("update-preview", update_file_preview, preview)

        # run dialog
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            filename = unicode_gtk(dialog.get_filename())
            dialog.destroy()
            if filename is None:
                return

            # TODO: do I need this?
            imgname, ext = os.path.splitext(os.path.basename(filename))
            if ext.lower() in (u".jpg", u".jpeg"):
                ext = u".jpg"
            else:
                ext = u".png"

            imgname2 = self._page.new_filename(imgname, ext=ext)

            try:
                self.insert_image(filename, imgname2)
            except Exception, e:
                # TODO: make exception more specific
                self.emit("error",
                          _("Could not insert image '%s'") % filename, e)
        else:
            dialog.destroy()

    def insert_image(self, filename, savename=u"image.png"):
        """Inserts an image into the text editor"""
        if self._page is None:
            return

        img = RichTextImage()
        img.set_from_pixbuf(gdk.pixbuf_new_from_file(filename))
        self._textview.insert_image(img, savename)

    #=================================================
    # Image context menu

    def view_image(self, image_filename):
        current_page = self._page
        if current_page is None:
            return

        image_path = os.path.join(current_page.get_path(), image_filename)
        self._app.run_external_app("image_viewer", image_path)

    def _on_view_image(self, menuitem):
        """View image in Image Viewer"""
        # get image filename
        image_filename = menuitem.get_parent().get_child().get_filename()
        self.view_image(image_filename)

    def _on_edit_image(self, menuitem):
        """Edit image in Image Editor"""
        current_page = self._page
        if current_page is None:
            return

        # get image filename
        image_filename = menuitem.get_parent().get_child().get_filename()
        image_path = os.path.join(current_page.get_path(), image_filename)
        self._app.run_external_app("image_editor", image_path)

    def _on_resize_image(self, menuitem):
        """Resize image"""

        current_page = self._page
        if current_page is None:
            return

        image = menuitem.get_parent().get_child()
        image_resize_dialog = \
            dialog_image_resize.ImageResizeDialog(self.get_toplevel(),
                                                  self._app.pref)
        image_resize_dialog.on_resize(image)

    def _on_new_image(self):
        """New image"""
        current_page = self._page
        if current_page is None:
            return

        dialog = dialog_image_new.NewImageDialog(self, self._app)
        dialog.show()

    def _on_save_image_as(self, menuitem):
        """Save image as a new file"""
        current_page = self._page
        if current_page is None:
            return

        # get image filename
        image = menuitem.get_parent().get_child()

        dialog = FileChooserDialog(
            _("Save Image As..."), self.get_toplevel(),
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Save"), gtk.RESPONSE_OK),
            app=self._app,
            persistent_path="save_image_path")
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            if not dialog.get_filename():
                self.emit("error", _("Must specify a filename for the image."),
                          None)
            else:
                filename = unicode_gtk(dialog.get_filename())
                try:
                    image.write(filename)
                except Exception:
                    self.emit("error", _("Could not save image '%s'.")
                              % filename, None)

        dialog.destroy()

    def make_image_menu(self, menu):
        """image context menu"""

        # TODO: convert into UIManager?
        # TODO: move to EditorMenus?
        # TODO: add accelerators back
        menu.set_accel_path(CONTEXT_MENU_ACCEL_PATH)
        item = gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)

        # image/edit
        item = gtk.MenuItem(_("_View Image..."))
        item.connect("activate", self._on_view_image)
        item.child.set_markup_with_mnemonic(_("<b>_View Image...</b>"))
        item.show()
        menu.append(item)

        item = gtk.MenuItem(_("_Edit Image..."))
        item.connect("activate", self._on_edit_image)
        item.show()
        menu.append(item)

        item = gtk.MenuItem(_("_Resize Image..."))
        item.connect("activate", self._on_resize_image)
        item.show()
        menu.append(item)

        # image/save
        item = gtk.ImageMenuItem(_("_Save Image As..."))
        item.connect("activate", self._on_save_image_as)
        item.show()
        menu.append(item)


class FontUI (object):

    def __init__(self, widget, signal, update_func=lambda ui, font: None,
                 block=None, unblock=None):
        self.widget = widget
        self.signal = signal
        self.update_func = update_func

        if block is None:
            self.block = lambda: self.widget.handler_block(self.signal)
        else:
            self.block = block

        if unblock is None:
            self.unblock = lambda: self.widget.handler_unblock(self.signal)
        else:
            self.unblock = unblock


class EditorMenus (gobject.GObject):

    def __init__(self, app, editor):
        gobject.GObject.__init__(self)

        self._editor = editor
        self._app = app
        self._action_group = None
        self._uis = []
        self._font_ui_signals = []     # list of font ui widgets
        self.spell_check_toggle = None

        self._removed_widgets = []

    #=============================================================
    # Update UI (menubar) from font under cursor

    def on_font_change(self, editor, font):
        """Update the toolbar reflect the font under the cursor"""
        # block toolbar handlers
        for ui in self._font_ui_signals:
            ui.block()

        # call update callback
        for ui in self._font_ui_signals:
            ui.update_func(ui, font)

        # unblock toolbar handlers
        for ui in self._font_ui_signals:
            ui.unblock()

    #==================================================
    # changing font handlers

    def _on_mod(self, mod):
        """Toggle a font modification"""
        self._editor.get_textview().toggle_font_mod(mod)

    def _on_toggle_link(self):
        """Link mode has been toggled"""
        textview = self._editor.get_textview()
        textview.toggle_link()
        tag, start, end = textview.get_link()

        if tag is not None:
            url = start.get_text(end)
            if tag.get_href() == "" and is_url(url):
                # set default url to link text
                textview.set_link(url, start, end)
            self._editor.emit("make-link")

    def _on_justify(self, justify):
        """Set font justification"""
        self._editor.get_textview().set_justify(justify)
        #font = self._editor.get_textview().get_font()
        #self.on_font_change(self._editor, font)

    def _on_bullet_list(self):
        """Toggle bullet list"""
        self._editor.get_textview().toggle_bullet()
        #font = self._editor.get_textview().get_font()
        #self.on_font_change(self._editor, font)

    def _on_indent(self):
        """Indent current paragraph"""
        self._editor.get_textview().indent()

    def _on_unindent(self):
        """Unindent current paragraph"""
        self._editor.get_textview().unindent()

    def _on_family_set(self, font_family_combo):
        """Set the font family"""
        self._editor.get_textview().set_font_family(
            font_family_combo.get_family())
        self._editor.get_textview().grab_focus()

    def _on_font_size_change(self, size):
        """Set the font size"""
        self._editor.get_textview().set_font_size(size)
        self._editor.get_textview().grab_focus()

    def _on_font_size_inc(self):
        """Increase font size"""
        font = self._editor.get_textview().get_font()
        font.size += 2
        self._editor.get_textview().set_font_size(font.size)
        #self.on_font_change(self._editor, font)

    def _on_font_size_dec(self):
        """Decrease font size"""
        font = self._editor.get_textview().get_font()
        if font.size > 4:
            font.size -= 2
        self._editor.get_textview().set_font_size(font.size)
        #self.on_font_change(self._editor, font)

    def _on_color_set(self, kind, widget, color=0):
        """Set text/background color"""
        if color == 0:
            color = widget.color

        if kind == "fg":
            self._editor.get_textview().set_font_fg_color(color)
        elif kind == "bg":
            self._editor.get_textview().set_font_bg_color(color)
        else:
            raise Exception("unknown color type '%s'" % str(kind))

    def _on_colors_set(self, colors):
        """Set color pallete"""
        # save colors
        notebook = self._editor._notebook
        if notebook:
            notebook.pref.set("colors", list(colors))
            notebook.set_preferences_dirty()

        self._app.get_listeners("colors_changed").notify(notebook, colors)

    def _on_choose_font(self):
        """Callback for opening Choose Font Dialog"""
        font = self._editor.get_textview().get_font()

        dialog = gtk.FontSelectionDialog(_("Choose Font"))
        dialog.set_font_name("%s %d" % (font.family, font.size))
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            self._editor.get_textview().set_font(dialog.get_font_name())
            self._editor.get_textview().grab_focus()

        dialog.destroy()

    #=======================================================
    # spellcheck

    def enable_spell_check(self, enabled):
        """Spell check"""
        self._editor.get_textview().enable_spell_check(enabled)

        # see if spell check became enabled
        enabled = self._editor.get_textview().is_spell_check_enabled()

        # update UI to match
        if self.spell_check_toggle:
            self.spell_check_toggle.set_active(enabled)

        return enabled

    def on_spell_check_toggle(self, widget):
        """Toggle spell checker"""
        self.enable_spell_check(widget.get_active())

    #=====================================================
    # toolbar and menus

    def add_ui(self, window):
        self._action_group = gtk.ActionGroup("Editor")
        self._uis = []
        add_actions(self._action_group, self.get_actions())
        window.get_uimanager().insert_action_group(
            self._action_group, 0)

        for s in self.get_ui():
            self._uis.append(window.get_uimanager().add_ui_from_string(s))
        window.get_uimanager().ensure_update()

        self.setup_menu(window, window.get_uimanager())

    def remove_ui(self, window):

        # disconnect signals
        for ui in self._font_ui_signals:
            ui.widget.disconnect(ui.signal)
        self._font_ui_signals = []

        # remove ui
        for ui in reversed(self._uis):
            window.get_uimanager().remove_ui(ui)
        self._uis = []
        #window.get_uimanager().ensure_update()

        # remove action group
        window.get_uimanager().remove_action_group(self._action_group)
        self._action_group = None

    def get_actions(self):

        def BothAction(name1, *args):
            return [Action(name1, *args), ToggleAction(name1 + " Tool", *args)]

        return (map(lambda x: Action(*x), [
            ("Insert Horizontal Rule", None, _("Insert _Horizontal Rule"),
             "<control>H", None,
             lambda w: self._editor.on_insert_hr()),

            ("Insert Image", None, _("Insert _Image..."),
             "", None,
             lambda w: self._editor.on_insert_image()),

            ("Insert New Image", None, _("Insert _New Image..."),
             "", _("Insert a new image"),
             lambda w: self._on_new_image()),

            ("Insert Screenshot", None, _("Insert _Screenshot..."),
             "<control>Insert", None,
             lambda w: self._editor.on_screenshot()),

            # finding
            ("Find In Page", gtk.STOCK_FIND, _("_Find In Page..."),
             "<control>F", None,
             lambda w: self._editor.find_dialog.on_find(False)),

            ("Find Next In Page", gtk.STOCK_FIND, _("Find _Next In Page..."),
             "<control>G", None,
             lambda w: self._editor.find_dialog.on_find(False, forward=True)),

            ("Find Previous In Page", gtk.STOCK_FIND,
             _("Find Pre_vious In Page..."),
             "<control><shift>G", None,
             lambda w: self._editor.find_dialog.on_find(False, forward=False)),

            ("Replace In Page", gtk.STOCK_FIND_AND_REPLACE,
             _("_Replace In Page..."),
             "<control>R", None,
             lambda w: self._editor.find_dialog.on_find(True)),

            ("Format", None, _("Fo_rmat"))]) +

            BothAction("Bold", gtk.STOCK_BOLD, _("_Bold"),
                       "<control>B", _("Bold"),
                       lambda w: self._on_mod("bold"),
                       "bold.png") +

            BothAction("Italic", gtk.STOCK_ITALIC, _("_Italic"),
                       "<control>I", _("Italic"),
                       lambda w: self._on_mod("italic"),
                       "italic.png") +

            BothAction("Underline", gtk.STOCK_UNDERLINE, _("_Underline"),
                       "<control>U", _("Underline"),
                       lambda w: self._on_mod("underline"),
                       "underline.png") +

            BothAction("Strike", None, _("S_trike"),
                       "", _("Strike"),
                       lambda w: self._on_mod("strike"),
                       "strike.png") +

            BothAction("Monospace", None, _("_Monospace"),
                       "<control>M", _("Monospace"),
                       lambda w: self._on_mod("tt"),
                       "fixed-width.png") +

            BothAction("Link", None, _("Lin_k"),
                       "<control>L", _("Make Link"),
                       lambda w: self._on_toggle_link(),
                       "link.png") +

            BothAction("No Wrapping", None, _("No _Wrapping"),
                       "", _("No Wrapping"),
                       lambda w: self._on_mod("nowrap"),
                       "no-wrap.png") +

            BothAction("Left Align", None, _("_Left Align"),
                       "<shift><control>L", _("Left Align"),
                       lambda w: self._on_justify("left"),
                       "alignleft.png") +

            BothAction("Center Align", None, _("C_enter Align"),
                       "<shift><control>E", _("Center Align"),
                       lambda w: self._on_justify("center"),
                       "aligncenter.png") +

            BothAction("Right Align", None, _("_Right Align"),
                       "<shift><control>R", _("Right Align"),
                       lambda w: self._on_justify("right"),
                       "alignright.png") +

            BothAction("Justify Align", None, _("_Justify Align"),
                       "<shift><control>J", _("Justify Align"),
                       lambda w: self._on_justify("fill"),
                       "alignjustify.png") +

            BothAction("Bullet List", None, _("_Bullet List"),
                       "<control>asterisk", _("Bullet List"),
                       lambda w: self._on_bullet_list(),
                       "bullet.png") +

            map(lambda x: Action(*x), [

                ("Font Selector Tool", None, "", "", _("Set Font Face")),
                ("Font Size Tool", None, "", "", _("Set Font Size")),
                ("Font Fg Color Tool", None, "", "", _("Set Text Color")),
                ("Font Bg Color Tool", None, "", "",
                 _("Set Background Color")),

                ("Indent More", None, _("Indent M_ore"),
                 "<control>parenright", None,
                 lambda w: self._on_indent(),
                 "indent-more.png"),

                ("Indent Less", None, _("Indent Le_ss"),
                 "<control>parenleft", None,
                 lambda w: self._on_unindent(),
                 "indent-less.png"),

                ("Increase Font Size", None, _("Increase Font _Size"),
                 "<control>equal", None,
                 lambda w: self._on_font_size_inc()),

                ("Decrease Font Size", None, _("_Decrease Font Size"),
                 "<control>minus", None,
                 lambda w: self._on_font_size_dec()),

                ("Apply Text Color", None, _("_Apply Text Color"),
                 "", None,
                 lambda w: self._on_color_set("fg", self.fg_color_button),
                 "font-inc.png"),

                ("Apply Background Color", None, _("A_pply Background Color"),
                 "", None,
                 lambda w: self._on_color_set("bg", self.bg_color_button),
                 "font-dec.png"),

                ("Choose Font", None, _("Choose _Font"),
                 "<control><shift>F", None,
                 lambda w: self._on_choose_font(),
                 "font.png"),

                ("Go to Link", None, _("Go to Lin_k"),
                 "<control>space", None,
                 lambda w: self._editor.get_textview().click_iter()),

                ]) +

            [ToggleAction("Spell Check", None, _("_Spell Check"),
                          "", None,
                          self.on_spell_check_toggle)]
        )

    def get_ui(self):

        use_minitoolbar = self._app.pref.get("look_and_feel",
                                             "use_minitoolbar",
                                             default=False)

        ui = ["""
        <ui>
        <menubar name="main_menu_bar">
          <menu action="Edit">
            <placeholder name="Viewer">
              <placeholder name="Editor">
                <menuitem action="Insert Horizontal Rule"/>
                <menuitem action="Insert Image"/>
              <!--  <menuitem action="Insert New Image"/> -->
                <menuitem action="Insert Screenshot"/>
                <placeholder name="Extension"/>
              </placeholder>
            </placeholder>
          </menu>
          <menu action="Search">
            <placeholder name="Viewer">
              <placeholder name="Editor">
                <menuitem action="Find In Page"/>
                <menuitem action="Find Next In Page"/>
                <menuitem action="Find Previous In Page"/>
                <menuitem action="Replace In Page"/>
              </placeholder>
            </placeholder>
          </menu>
          <placeholder name="Viewer">
            <placeholder name="Editor">
                <menu action="Format">
                <menuitem action="Bold"/>
                <menuitem action="Italic"/>
                <menuitem action="Underline"/>
                <menuitem action="Strike"/>
                <menuitem action="Monospace"/>
                <menuitem action="Link"/>
                <menuitem action="No Wrapping"/>
                <separator/>
                <menuitem action="Left Align"/>
                <menuitem action="Center Align"/>
                <menuitem action="Right Align"/>
                <menuitem action="Justify Align"/>
                <menuitem action="Bullet List"/>
                <menuitem action="Indent More"/>
                <menuitem action="Indent Less"/>
                <separator/>
                <menuitem action="Increase Font Size"/>
                <menuitem action="Decrease Font Size"/>
                <menuitem action="Apply Text Color"/>
                <menuitem action="Apply Background Color"/>
                <menuitem action="Choose Font"/>
              </menu>
            </placeholder>
          </placeholder>

          <menu action="Go">
            <placeholder name="Viewer">
              <placeholder name="Editor">
                <menuitem action="Go to Link"/>
              </placeholder>
            </placeholder>
          </menu>

          <menu action="Tools">
            <placeholder name="Viewer">
              <menuitem action="Spell Check"/>
            </placeholder>
          </menu>
        </menubar>
     </ui>
        """]

        if use_minitoolbar:
            ui.append("""
        <ui>
        <toolbar name="main_tool_bar">
          <placeholder name="Viewer">
            <placeholder name="Editor">
              <toolitem action="Bold Tool"/>
              <toolitem action="Italic Tool"/>
              <toolitem action="Underline Tool"/>
              <toolitem action="Link Tool"/>
              <toolitem action="Font Selector Tool"/>
              <toolitem action="Font Size Tool"/>
              <toolitem action="Font Fg Color Tool"/>
              <toolitem action="Font Bg Color Tool"/>
              <separator/>
              <toolitem action="Bullet List Tool"/>
            </placeholder>
          </placeholder>
        </toolbar>

        </ui>
        """)
        else:
            ui.append("""
        <ui>
        <toolbar name="main_tool_bar">
          <placeholder name="Viewer">
            <placeholder name="Editor">
              <toolitem action="Bold Tool"/>
              <toolitem action="Italic Tool"/>
              <toolitem action="Underline Tool"/>
              <toolitem action="Strike Tool"/>
              <toolitem action="Monospace Tool"/>
              <toolitem action="Link Tool"/>
              <toolitem action="No Wrapping Tool"/>

              <toolitem action="Font Selector Tool"/>
              <toolitem action="Font Size Tool"/>
              <toolitem action="Font Fg Color Tool"/>
              <toolitem action="Font Bg Color Tool"/>

              <separator/>
              <toolitem action="Left Align Tool"/>
              <toolitem action="Center Align Tool"/>
              <toolitem action="Right Align Tool"/>
              <toolitem action="Justify Align Tool"/>
              <toolitem action="Bullet List Tool"/>
              <separator/>
            </placeholder>
          </placeholder>
        </toolbar>

        </ui>
        """)

        return ui

    def setup_font_toggle(self, uimanager, path, stock=False,
                          update_func=lambda ui, font: None):

        action = uimanager.get_action(path)
        # NOTE: action can be none if minimal toolbar is in use.

        if action:
            proxies = action.get_proxies()
            if len(proxies) == 0:
                return None
            # NOTE: sometimes get_proxies() is zero length after app options
            # OK button is clicked.  Don't know why this happens yet.
            widget = action.get_proxies()[0]

            def block():
                action.handler_block(action.signal)
                action.block_activate_from(widget)

            def unblock():
                action.handler_unblock(action.signal)
                action.unblock_activate_from(widget)

            ui = FontUI(action, action.signal, update_func,
                        block=block,
                        unblock=unblock)
            self._font_ui_signals.append(ui)
            return ui
        else:
            return None

    def setup_menu(self, window, uimanager):

        def update_toggle(ui, active):
            if len(ui.widget.get_proxies()) > 0:
                widget = ui.widget.get_proxies()[0]
                widget.set_active(active)

        def replace_widget(path, widget):
            w = uimanager.get_widget(path)
            if w:
                self._removed_widgets.append(w.child)
                w.remove(w.child)
                w.add(widget)
                widget.show()
                w.set_homogeneous(False)

        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Bold Tool",
            update_func=lambda ui, font: update_toggle(ui, font.mods["bold"]))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Italic Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.mods["italic"]))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Underline Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.mods["underline"]))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Strike Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.mods["strike"]))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Monospace Tool",
            update_func=lambda ui, font: update_toggle(ui, font.mods["tt"]))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Link Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.link is not None))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/No Wrapping Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.mods["nowrap"]))

        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Left Align Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.justify == "left"))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Center Align Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.justify == "center"))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Right Align Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.justify == "right"))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Justify Align Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.justify == "fill"))
        self.setup_font_toggle(
            uimanager, "/main_tool_bar/Viewer/Editor/Bullet List Tool",
            update_func=lambda ui, font:
            update_toggle(ui, font.par_type == "bullet"))

        # family combo
        font_family_combo = FontSelector()
        font_family_combo.set_size_request(150, 25)
        replace_widget("/main_tool_bar/Viewer/Editor/Font Selector Tool",
                       font_family_combo)
        font_family_id = font_family_combo.connect("changed",
                                                   self._on_family_set)
        self._font_ui_signals.append(
            FontUI(font_family_combo,
                   font_family_id,
                   update_func=lambda ui, font:
                   ui.widget.set_family(font.family)))

        # font size
        DEFAULT_FONT_SIZE = 10
        font_size_button = gtk.SpinButton(
            gtk.Adjustment(value=DEFAULT_FONT_SIZE, lower=2, upper=500,
                           step_incr=1))
        font_size_button.set_size_request(-1, 25)
        font_size_button.set_value(DEFAULT_FONT_SIZE)
        font_size_button.set_editable(False)
        replace_widget("/main_tool_bar/Viewer/Editor/Font Size Tool",
                       font_size_button)

        font_size_id = font_size_button.connect(
            "value-changed",
            lambda w:
            self._on_font_size_change(font_size_button.get_value()))
        self._font_ui_signals.append(
            FontUI(font_size_button,
                   font_size_id,
                   update_func=lambda ui, font:
                   ui.widget.set_value(font.size)))

        def on_new_colors(notebook, colors):
            if self._editor.get_notebook() == notebook:
                self.fg_color_button.set_colors(colors)
                self.bg_color_button.set_colors(colors)
        self._app.get_listeners("colors_changed").add(on_new_colors)

        # init colors
        notebook = self._editor.get_notebook()
        if notebook:
            colors = notebook.pref.get("colors", default=DEFAULT_COLORS)
        else:
            colors = DEFAULT_COLORS

        # font fg color
        # TODO: code in proper default color
        self.fg_color_button = FgColorTool(14, 15, "#000000")
        self.fg_color_button.set_colors(colors)
        self.fg_color_button.set_homogeneous(False)
        self.fg_color_button.connect(
            "set-color",
            lambda w, color: self._on_color_set(
                "fg", self.fg_color_button, color))
        self.fg_color_button.connect(
            "set-colors",
            lambda w, colors: self._on_colors_set(colors))
        replace_widget("/main_tool_bar/Viewer/Editor/Font Fg Color Tool",
                       self.fg_color_button)

        # font bg color
        self.bg_color_button = BgColorTool(14, 15, "#ffffff")
        self.bg_color_button.set_colors(colors)
        self.bg_color_button.set_homogeneous(False)
        self.bg_color_button.connect(
            "set-color",
            lambda w, color: self._on_color_set(
                "bg", self.bg_color_button, color))
        self.bg_color_button.connect(
            "set-colors",
            lambda w, colors: self._on_colors_set(colors))
        replace_widget("/main_tool_bar/Viewer/Editor/Font Bg Color Tool",
                       self.bg_color_button)

        # get spell check toggle
        self.spell_check_toggle = \
            uimanager.get_widget("/main_menu_bar/Tools/Viewer/Spell Check")
        self.spell_check_toggle.set_sensitive(
            self._editor.get_textview().can_spell_check())
        self.spell_check_toggle.set_active(window.get_app().pref.get(
            "editors", "general", "spell_check", default=True))


class ComboToolItem(gtk.ToolItem):

    __gtype_name__ = "ComboToolItem"

    def __init__(self):
        gtk.ToolItem.__init__(self)

        self.set_border_width(2)
        self.set_homogeneous(False)
        self.set_expand(False)

        self.combobox = gtk.combo_box_entry_new_text()
        for text in ['a', 'b', 'c', 'd', 'e', 'f']:
            self.combobox.append_text(text)
        self.combobox.show()
        self.add(self.combobox)

    def do_set_tooltip(self, tooltips, tip_text=None, tip_private=None):
        gtk.ToolItem.set_tooltip(self, tooltips, tip_text, tip_private)

        tooltips.set_tip(self.combobox, tip_text, tip_private)


class ComboToolAction(gtk.Action):

    __gtype_name__ = "ComboToolAction"

    def __init__(self, name, label, tooltip, stock_id):
        gtk.Action.__init__(self, name, label, tooltip, stock_id)


ComboToolAction.set_tool_item_type(ComboToolItem)
