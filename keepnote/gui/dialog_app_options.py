"""

    KeepNote
    Application Options Dialog

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@mit.edu>
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
import sys
import gettext

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk.glade
from gtk import gdk

# keepnote imports
import keepnote
from keepnote import unicode_gtk
from keepnote import get_resource
from keepnote.gui.font_selector import FontSelector
import keepnote.gui
from keepnote.gui.icons import get_icon_filename
import keepnote.trans
import keepnote.gui.extension

_ = keepnote.translate




def on_browse(parent, title, filename, entry,
              action=gtk.FILE_CHOOSER_ACTION_OPEN):
    """Callback for selecting file browser associated with a text entry"""

    dialog = gtk.FileChooserDialog(title, parent, 
        action=action,
        buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                 _("Open"), gtk.RESPONSE_OK))
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    # set the filename if it is fully specified
    if filename == "":
        filename = entry.get_text()
    if os.path.isabs(filename):            
        dialog.set_filename(filename)

    if dialog.run() == gtk.RESPONSE_OK and dialog.get_filename():
        entry.set_text(dialog.get_filename())

    dialog.destroy()


class Section (object):
    """A Section in the Options Dialog"""

    def __init__(self, key, dialog, app, label=u"", icon=None):
        self.key = key
        self.dialog = dialog
        self.label = label
        self.icon = icon

        self.frame = gtk.Frame("")
        self.frame.get_label_widget().set_text("<b>%s</b>" % label)
        self.frame.get_label_widget().set_use_markup(True)
        self.frame.set_property("shadow-type", gtk.SHADOW_NONE)

        self.__align = gtk.Alignment()
        self.__align.set_padding(10, 0, 10, 0)
        self.__align.show()
        self.frame.add(self.__align)


    def get_default_widget(self):
        """Returns the default parent widget for a Section"""
        return self.__align


    def load_options(self, app):
        """Load options from app to UI"""
        pass

    def save_options(self, app):
        """Save options to the app"""
        pass


class GeneralSection (Section):

    def __init__(self, key, dialog, app,
                 label=u"", icon="keepnote-16x16.png"):
        Section.__init__(self, key, dialog, app, label, icon)
        
        self.notebook = None
        
        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "general_frame", keepnote.GETTEXT_DOMAIN)
        self.xml.signal_autoconnect(self)
        self.xml.signal_autoconnect({
            "on_default_notebook_button_clicked":
                lambda w: on_browse(self.dialog,
                    _("Choose Default Notebook"),
                    "",
                    self.xml.get_widget("default_notebook_entry")),
            })
        self.frame = self.xml.get_widget("general_frame")



    def on_default_notebook_radio_changed(self, radio):
        """Default notebook radio changed"""
        no_default = self.xml.get_widget("no_default_notebook_radio")
        default = self.xml.get_widget("default_notebook_radio")
        last = self.xml.get_widget("last_notebook_radio")

        default_tab = self.xml.get_widget("default_notebook_table")
        default_tab.set_sensitive(default.get_active())
            

    def on_autosave_check_toggled(self, widget):
        """The autosave option controls sensitivity of autosave time"""
        self.xml.get_widget("autosave_entry").set_sensitive(
            widget.get_active())
        self.xml.get_widget("autosave_label").set_sensitive(
            widget.get_active())


    def on_systray_check_toggled(self, widget):
        """Systray option controls sensitivity of skip taskbar"""
        self.xml.get_widget("skip_taskbar_check").set_sensitive(
            widget.get_active())
        
    
    def on_set_default_notebook_button_clicked(self, widget):

        if self.notebook:
            self.xml.get_widget("default_notebook_entry").set_text(
                self.notebook.get_path())


    def load_options(self, app):
        
        win = app.get_current_window()
        if win:
            self.notebook = win.get_notebook()

        # populate default notebook        
        if app.pref.use_last_notebook:
            self.xml.get_widget("last_notebook_radio").set_active(True)
        elif app.pref.default_notebook == "":
            self.xml.get_widget("no_default_notebook_radio").set_active(True)
        else:
            self.xml.get_widget("default_notebook_radio").set_active(True)
            self.xml.get_widget("default_notebook_entry").\
                set_text(app.pref.default_notebook)



        # populate autosave
        self.xml.get_widget("autosave_check").set_active(
            app.pref.autosave)
        self.xml.get_widget("autosave_entry").set_text(
            str(int(app.pref.autosave_time / 1000)))

        self.xml.get_widget("autosave_entry").set_sensitive(
            app.pref.autosave)
        self.xml.get_widget("autosave_label").set_sensitive(
            app.pref.autosave)


        # use systray icon
        self.xml.get_widget("systray_check").set_active(app.pref.use_systray)
        self.xml.get_widget("skip_taskbar_check").set_active(app.pref.skip_taskbar)
        self.xml.get_widget("skip_taskbar_check").set_sensitive(app.pref.use_systray)


    def save_options(self, app):
        if self.xml.get_widget("last_notebook_radio").get_active():
            app.pref.use_last_notebook = True
        elif self.xml.get_widget("default_notebook_radio").get_active():
            app.pref.use_last_notebook = False
            app.pref.default_notebook = \
                unicode_gtk(self.xml.get_widget("default_notebook_entry").get_text())
        else:
            app.pref.use_last_notebook = False
            app.pref.default_notebook = ""


        # save autosave
        app.pref.autosave = \
            self.xml.get_widget("autosave_check").get_active()
        try:
            app.pref.autosave_time = \
                int(self.xml.get_widget("autosave_entry").get_text()) * 1000
        except:
            pass

        # use systray icon
        app.pref.use_systray = self.xml.get_widget("systray_check").get_active()
        app.pref.skip_taskbar = self.xml.get_widget("skip_taskbar_check").get_active()


class LookAndFeelSection (Section):
    
    def __init__(self, key, dialog, app, label=u"", icon="lookandfeel.png"):
        Section.__init__(self, key, dialog, app, label, icon)

        w = self.get_default_widget()
        v = gtk.VBox(False, 5)
        v.show()
        w.add(v)

        def add_check(label):
            c = gtk.CheckButton(label)
            c.show()
            v.pack_start(c, False, False, 0)
            return c

        self.treeview_lines_check = add_check(
            _("show lines in treeview"))
        self.listview_rules_check = add_check(
            _("use ruler hints in listview"))
        self.use_stock_icons_check = add_check(
            _("use GTK stock icons in toolbar"))
        self.use_minitoolbar = add_check(
            _("use minimal toolbar"))
        
        # view mode combo
        h = gtk.HBox(False, 5); h.show()
        l = gtk.Label(_("Listview Layout:")); l.show()
        h.pack_start(l, False, False, 0)
        c = gtk.combo_box_new_text(); c.show()
        c.append_text(_("Vertical"))
        c.append_text(_("Horizontal"))
        h.pack_start(c, False, False, 0)
        v.pack_start(h)
        self.listview_layout = c
        


    def load_options(self, app):

        self.treeview_lines_check.set_active(app.pref.treeview_lines)
        self.listview_rules_check.set_active(app.pref.listview_rules)
        self.use_stock_icons_check.set_active(app.pref.use_stock_icons)
        self.use_minitoolbar.set_active(app.pref.use_minitoolbar)

        if app.pref.view_mode == "horizontal":
            self.listview_layout.set_active(1)
        else:
            self.listview_layout.set_active(0)
            


    def save_options(self, app):
        
        app.pref.treeview_lines = self.treeview_lines_check.get_active()
        app.pref.listview_rules = self.listview_rules_check.get_active()
        app.pref.use_stock_icons = self.use_stock_icons_check.get_active()
        app.pref.use_minitoolbar = self.use_minitoolbar.get_active()

        app.pref.view_mode = ["vertical", "horizontal"][
            self.listview_layout.get_active()]
 

class LanguageSection (Section):
    
    def __init__(self, key, dialog, app, label=u"", icon=None):
        Section.__init__(self, key, dialog, app, label, icon)

        w = self.get_default_widget()
        v = gtk.VBox(False, 5)
        v.show()
        w.add(v)        
        
        # language combo
        h = gtk.HBox(False, 5); h.show()
        l = gtk.Label(_("Language:")); l.show()
        h.pack_start(l, False, False, 0)
        c = gtk.combo_box_new_text(); c.show()

        # populate language options
        c.append_text("default")
        for lang in keepnote.trans.get_langs():
            c.append_text(lang)
        
        # pack combo
        h.pack_start(c, False, False, 0)
        v.pack_start(h)
        self.language_box = c
        


    def load_options(self, app):

        # set default
        if app.pref.language == "":
            self.language_box.set_active(0)
        else:
            for i, row in enumerate(self.language_box.get_model()):
                if app.pref.language == row[0]:
                    self.language_box.set_active(i)
                    break


    def save_options(self, app):
        
        if self.language_box.get_active() > 0:
            app.pref.language = lang = self.language_box.get_active_text()
        else:
            # set default
            app.pref.language = ""

        # XXX: may be I should not change translation during execution
        #if app.pref.language != keepnote.trans.get_lang():
        #    keepnote.trans.set_lang(app.pref.language)
 



class HelperAppsSection (Section):
    
    def __init__(self, key, dialog, app, label=u"", icon=None):
        Section.__init__(self, key, dialog, app, label, icon)
        
        self.entries = {}
        w = self.get_default_widget()
        
        self.table = gtk.Table(len(app.pref.external_apps), 2)
        self.table.show()
        w.add(self.table)

        # set icon
        try:
            self.icon = keepnote.gui.get_pixbuf(get_icon_filename(gtk.STOCK_EXECUTE), size=(15, 15))
        except:
            pass


        
    def load_options(self, app):

        # clear table, resize
        self.table.foreach(lambda x: self.table.remove(x))
        self.table.resize(len(app.pref.external_apps), 2)

        for i, app in enumerate(app.pref.external_apps):
            key = app.key
            app_title = app.title
            prog = app.prog
            
            # program label
            label = gtk.Label(app_title +":")
            label.set_justify(gtk.JUSTIFY_RIGHT)
            label.set_alignment(1.0, 0.5)
            label.show()
            self.table.attach(label, 0, 1, i, i+1,
                         xoptions=gtk.FILL, yoptions=0,
                         xpadding=2, ypadding=2)

            # program entry
            entry = gtk.Entry()
            entry.set_text(prog)
            entry.set_width_chars(30)
            entry.show()
            self.entries[key] = entry
            self.table.attach(entry, 1, 2, i, i+1,
                         xoptions=gtk.FILL | gtk.EXPAND, yoptions=0,
                         xpadding=2, ypadding=2)

            # browse button
            def button_clicked(key, title, prog):
                return lambda w: \
                    on_browse(self.dialog,
                              _("Choose %s") % title,
                              "", self.entries[key])
            button = gtk.Button(_("Browse..."))
            button.set_image(
                gtk.image_new_from_stock(gtk.STOCK_OPEN,
                                         gtk.ICON_SIZE_SMALL_TOOLBAR))
            button.show()
            button.connect("clicked", button_clicked(key, app_title, prog))
            self.table.attach(button, 2, 3, i, i+1,
                         xoptions=0, yoptions=0,
                         xpadding=2, ypadding=2)
    

    def save_options(self, app):

        # TODO: use a public interface

        # save external app options
        for key, entry in self.entries.iteritems():
            if key in app.pref._external_apps_lookup:
                app.pref._external_apps_lookup[key].prog = unicode_gtk(
                    entry.get_text())




class DatesSection (Section):
    
    def __init__(self, key, dialog, app, label=u"", icon="time.png"):
        Section.__init__(self, key, dialog, app, label, icon)

        self.date_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                   "date_time_frame", keepnote.GETTEXT_DOMAIN)
        self.date_xml.signal_autoconnect(self)
        self.frame = self.date_xml.get_widget("date_time_frame")


    def load_options(self, app):
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            self.date_xml.get_widget("date_%s_entry" % name).\
                set_text(app.pref.timestamp_formats[name])

    def save_options(self, app):
        # save date formatting
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            app.pref.timestamp_formats[name] = unicode_gtk(
                self.date_xml.get_widget("date_%s_entry" % name).get_text())
        

class AllNoteBooksSection (Section):
    
    def __init__(self, key, dialog, app, label=u"", icon="folder.png"):
        Section.__init__(self, key, dialog, app, label, icon)

        w = self.get_default_widget()
        l = gtk.Label(_("This section contains options that are saved on a per notebook basis (e.g. notebook-specific font).   A subsection will appear for each notebook that is currently opened."))
        l.set_line_wrap(True)
        w.add(l)
        w.show_all()


class NoteBookSection (Section):
    
    def __init__(self, key, dialog, app, notebook, label=u"", 
                 icon="folder.png"):
        Section.__init__(self, key, dialog, app, label, icon)
        self.entries = {}

        self.notebook = notebook

        # add notebook font widget
        self.notebook_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "notebook_frame", keepnote.GETTEXT_DOMAIN)
        self.notebook_xml.signal_autoconnect(self)
        self.frame = self.notebook_xml.get_widget("notebook_frame")

        notebook_font_spot = self.notebook_xml.get_widget("notebook_font_spot")
        self.notebook_font_family = FontSelector()
        notebook_font_spot.add(self.notebook_font_family)
        self.notebook_font_family.show()        

        # populate notebook font
        self.notebook_font_size = self.notebook_xml.get_widget("notebook_font_size")
        self.notebook_font_size.set_value(10)
        self.notebook_index_dir = self.notebook_xml.get_widget("index_dir_entry")
        self.notebook_xml.get_widget("index_dir_browse").connect(
            "clicked",
            lambda w: on_browse(self.dialog,
                _("Choose alternative notebook index directory"),
                "", self.notebook_index_dir,
                action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER))

        self.frame.show_all()



    def load_options(self, app):
        
        if self.notebook is not None:
            font = self.notebook.pref.default_font
            family, mods, size = keepnote.gui.richtext.parse_font(font)
            self.notebook_font_family.set_family(family)
            self.notebook_font_size.set_value(size)

            self.notebook_index_dir.set_text(self.notebook.pref.index_dir)


    def save_options(self, app):
        
        if self.notebook is not None:
            pref = self.notebook.pref

            # save notebook font        
            pref.default_font = "%s %d" % (
                self.notebook_font_family.get_family(),
                self.notebook_font_size.get_value())

            # alternative index directory
            pref.index_dir = self.notebook_index_dir.get_text()

        

class ExtensionsSection (Section):
    
    def __init__(self, key, dialog, app, label=u"", icon=None):
        Section.__init__(self, key, dialog, app, label, icon)
        
        self.app = app
        self.entries = {}
        self.frame = gtk.Frame("")
        self.frame.get_label_widget().set_text("<b>Extensions</b>")
        self.frame.get_label_widget().set_use_markup(True)
        self.frame.set_property("shadow-type", gtk.SHADOW_NONE)
        
        align = gtk.Alignment()
        align.set_padding(10, 0, 10, 0)
        align.show()
        self.frame.add(align)
        
        v = gtk.VBox(False, 0)
        v.show()
        align.add(v)

        # extension list scrollbar
        self.sw = gtk.ScrolledWindow()
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.sw.set_shadow_type(gtk.SHADOW_IN)
        self.sw.show()
        v.pack_start(self.sw, True, True, 0)
        
        # extension list
        self.extlist = gtk.VBox(False, 0)
        self.extlist.show()
        self.sw.add_with_viewport(self.extlist)

        # hbox
        h = gtk.HBox(False, 0)
        h.show()
        v.pack_start(h, True, True, 0)
        
        # install button
        self.install_button = gtk.Button("Install new extension")
        self.install_button.set_relief(gtk.RELIEF_NONE)
        self.install_button.modify_fg(gtk.STATE_NORMAL, gtk.gdk.Color(0, 0, 65535))
        self.install_button.connect("clicked", self._on_install)
        self.install_button.show()
        h.pack_start(self.install_button, False, True, 0)

        # set icon
        try:
            self.icon = keepnote.gui.get_pixbuf(get_icon_filename(gtk.STOCK_ADD), size=(15, 15))
        except:
            pass



    def load_options(self, app):

        # clear extension list
        self.extlist.foreach(self.extlist.remove)
        
        def callback(ext):
            return lambda w: self._on_uninstall(ext)

        # populate extension list
        exts = list(app.iter_extensions())
        d = {"user": 0, "system": 1}
        exts.sort(key=lambda e: (d.get(e.type, 10), e.name))
        for ext in exts:
            if ext.visible:
                p = ExtensionWidget(app, ext)
                p.uninstall_button.connect("clicked", callback(ext))
                p.show()
                self.extlist.pack_start(p, True, True, 0)
        
        # setup scroll bar size
        maxheight = 270 # TODO: make this more dynamic
        w, h = self.extlist.size_request()
        w2, h2 = self.sw.get_vscrollbar().size_request()
        self.sw.set_size_request(400, min(maxheight, h+10))


    def save_options(self, app):
        
        for widget in self.extlist:
            try:
                widget.ext.enable(widget.enabled)
            except Exception, e:
                keepnote.log_error(e)
            widget.update()


    def _on_uninstall(self, ext):
        if self.app.uninstall_extension(ext):
            self.load_options(self.app)


    def _on_install(self, widget):

        # open file dialog
        dialog = gtk.FileChooserDialog(
            _("Install New Extension"), self.dialog, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Open"), gtk.RESPONSE_OK))
        dialog.set_transient_for(self.dialog)
        dialog.set_modal(True)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.kne")
        file_filter.set_name(_("KeepNote Extension (*.kne)"))
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name(_("All files (*.*)"))
        dialog.add_filter(file_filter)

        response = dialog.run()

        if gtk.RESPONSE_OK and dialog.get_filename():
            # install extension
            self.app.install_extension(dialog.get_filename())
            self.load_options(self.app)

        dialog.destroy()



class ExtensionWidget (gtk.EventBox):
    def __init__(self, app, ext):
        gtk.EventBox.__init__(self)

        self.app = app
        self.enabled = ext.is_enabled()
        self.ext = ext

        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(65535, 65535, 65535))

        frame = gtk.Frame(None)
        frame.set_property("shadow-type", gtk.SHADOW_OUT)
        frame.show()
        self.add(frame)

        # name
        frame2 = gtk.Frame("")
        frame2.set_property("shadow-type", gtk.SHADOW_NONE)
        frame2.get_label_widget().set_text("<b>%s</b> (%s/%s)" % 
                                           (ext.name, ext.type,
                                            ext.key))
        frame2.get_label_widget().set_use_markup(True)
        frame2.show()
        frame.add(frame2)

        # margin
        align = gtk.Alignment()
        align.set_padding(10, 10, 10, 10)
        align.show()
        frame2.add(align)

        # vbox
        v = gtk.VBox(False, 5)
        v.show()
        align.add(v)

        # description
        l = gtk.Label(ext.description)
        l.set_justify(gtk.JUSTIFY_LEFT)
        l.set_alignment(0.0, 0.0)
        l.show()
        v.pack_start(l, True, True, 0)

        # hbox
        h = gtk.HBox(False, 0)
        h.show()
        v.pack_start(h, True, True, 0)

        # enable button
        self.enable_check = gtk.CheckButton("Enabled")
        self.enable_check.set_active(self.enabled)
        self.enable_check.show()
        self.enable_check.connect(
            "toggled", lambda w: self._on_enabled(ext))
        h.pack_start(self.enable_check, False, True, 0)

        # divider
        l = gtk.Label("|"); l.show()
        h.pack_start(l, False, True, 0)

        # uninstall button        
        self.uninstall_button = gtk.Button("Uninstall")
        self.uninstall_button.set_relief(gtk.RELIEF_NONE)
        self.uninstall_button.set_sensitive(app.can_uninstall(ext))
        self.uninstall_button.show()
        h.pack_start(self.uninstall_button, False, True, 0)



    def update(self):
        self.enable_check.set_active(self.ext.is_enabled())

    def _on_enabled(self, ext):
        self.enabled = self.enable_check.get_active()


        


#=============================================================================

class ApplicationOptionsDialog (object):
    """Application options"""
    
    def __init__(self, app):
        self.app = app
        self.parent = None

        self._sections = []
        
        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "app_options_dialog", keepnote.GETTEXT_DOMAIN)
        self.dialog = self.xml.get_widget("app_options_dialog")
        self.dialog.connect("delete-event", self._on_delete_event)
        self.tabs = self.xml.get_widget("app_options_tabs")
        self.xml.signal_autoconnect({
            "on_cancel_button_clicked": 
                lambda w: self.on_cancel_button_clicked(),
            "on_ok_button_clicked":
                lambda w: self.on_ok_button_clicked(),
            "on_apply_button_clicked":
                lambda w: self.on_apply_button_clicked()})

        # setup treeview
        self.overview = self.xml.get_widget("app_config_treeview")
        self.overview_store = gtk.TreeStore(str, object, gdk.Pixbuf)
        self.overview.set_model(self.overview_store)
        self.overview.connect("cursor-changed", self.on_overview_select)

        # create the treeview column
        column = gtk.TreeViewColumn()
        self.overview.append_column(column)
        cell_text = gtk.CellRendererText()
        cell_icon = gtk.CellRendererPixbuf()
        column.pack_start(cell_icon, True)
        column.add_attribute(cell_icon, 'pixbuf', 2)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 0)
        

        # add tabs
        self.add_default_sections()

    
    def show(self, parent, section=None):
        """Display application options"""
        
        self.parent = parent
        self.dialog.set_transient_for(parent)

        # add notebook options
        self.notebook_sections = [
            self.add_section(NoteBookSection("notebook_%d" % i, 
                                             self.dialog, self.app, 
                                             notebook,
                                             notebook.get_title()), 
                             "notebooks")
            for i, notebook in enumerate(self.app.iter_notebooks())]


        # add extension options
        self.extensions_ui = []
        for ext in self.app.iter_extensions(True):
            if isinstance(ext, keepnote.gui.extension.Extension):
                ext.on_add_options_ui(self)
                self.extensions_ui.append(ext)

        # populate options ui
        self.load_options(self.app)

        self.dialog.show()

        if section:
            try:
                self.overview.set_cursor(self.get_section_path(section))
            except:
                pass


    def finish(self):

        # remove extension options
        for ext in self.extensions_ui:
            if isinstance(ext, keepnote.gui.extension.Extension):
                ext.on_remove_options_ui(self)
        self.extensions_ui = []

        # remove notebook options
        for section in self.notebook_sections:
            self.remove_section(section.key)


    def add_default_sections(self):

        self.add_section(
            GeneralSection("general", self.dialog, self.app, 
                           keepnote.PROGRAM_NAME))
        self.add_section(
            LookAndFeelSection("look_and_feel", self.dialog, 
                               self.app, _("Look and Feel")), 
            "general")
        self.add_section(
            LanguageSection("language", self.dialog, self.app, 
                            _("Language")),
            "general")
        self.add_section(
            DatesSection("date_and_time", self.dialog, self.app, 
                         _("Date and Time")), 
            "general")
        self.add_section(
            HelperAppsSection("helper_apps", self.dialog, 
                              self.app, _("Helper Applications")), 
            "general")
        self.add_section(
            AllNoteBooksSection("notebooks", self.dialog, self.app, 
                                _("Notebook Options"), "folder.png"))
        self.add_section(
            ExtensionsSection("extensions", self.dialog, 
                              self.app, _("Extensions")))

    #=====================================
    # options

    def load_options(self, app):
        """Load options into sections"""
        
        for section in self._sections:
            section.load_options(self.app)

    
    def save_options(self, app):
        """Save the options from each section"""
        
        for section in self._sections:
            section.save_options(self.app)

        # notify application preference changes
        self.app.pref.changed.notify()

        # save noteboook preference changes
        for notebook in self.app.iter_notebooks():
            notebook.write_preferences()
            notebook.notify_change(False)


    #=====================================
    # section handling

    def add_section(self, section, parent=None):
        """Add a section to the Options Dialog"""
        
        # icon size
        size = (15, 15)

        # determine parent section
        if parent is not None:
            path = self.get_section_path(parent)
            it = self.overview_store.get_iter(path)
        else:
            it = None

        self._sections.append(section)
        self.tabs.insert_page(section.frame, tab_label=None)
        section.frame.show()
        section.frame.queue_resize()

        icon = section.icon
        if icon is None:
            icon = icon="note.png"
        
        if isinstance(icon, basestring):
            pixbuf = keepnote.gui.get_resource_pixbuf(icon, size=size)
        else:
            pixbuf = icon

        # add to overview
        it = self.overview_store.append(it, [section.label, section, pixbuf])
        path = self.overview_store.get_path(it)
        self.overview.expand_to_path(path)

        return section


    def remove_section(self, key):
        
        # remove from tabs
        section = self.get_section(key)
        if section:
            self.tabs.remove_page(self._sections.index(section))
            self._sections.remove(section)

        # remove from tree
        path = self.get_section_path(key)
        if path is not None:
            self.overview_store.remove(self.overview_store.get_iter(path))




    def get_section(self, key):
        """Returns the section for a key"""

        for section in self._sections:
            if section.key == key:
                return section
        return None

            
    def get_section_path(self, key):
        """Returns the TreeModel path for a section"""

        def walk(node):

            child = self.overview_store.iter_children(node)
            while child:
                row = self.overview_store[child]
                if row[1].key == key:
                    return row.path
                
                # recurse
                ret = walk(child)
                if ret:
                    return ret

                child = self.overview_store.iter_next(child)

            return None
        return walk(None)


    #==========================================================
    # callbacks

    def on_overview_select(self, overview):
        """Callback for changing topic in overview"""
        row, col = overview.get_cursor()
        if row is not None:
            section = self.overview_store[row][1]
            self.tabs.set_current_page(self._sections.index(section))


    def on_cancel_button_clicked(self):
        """Callback for cancel button"""
        self.dialog.hide()
        self.finish()

    
    def on_ok_button_clicked(self):
        """Callback for ok button"""
        self.save_options(self.app)
        self.dialog.hide()
        self.finish()


    def on_apply_button_clicked(self):
        """Callback for apply button"""
        self.save_options(self.app)

        # clean up and reshow dialog
        self.finish()
        self.show(self.parent)
        
    
    def _on_delete_event(self, widget, event):
        """Callback for window close"""
        self.dialog.hide()
        self.finish()
        self.dialog.stop_emission("delete-event")
        return True


