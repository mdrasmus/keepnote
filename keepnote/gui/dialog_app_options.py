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

_ = gettext.gettext



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

    def load_options(self, app, notebook):
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


    def load_options(self, app, notebook):

        self.notebook = notebook

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
    
    def __init__(self, key, dialog, app, label=u"", icon=None):
        Section.__init__(self, key, dialog, app, label, icon)

        self.look_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                      "look_frame", keepnote.GETTEXT_DOMAIN)
        self.look_xml.signal_autoconnect(self)
        self.frame = self.look_xml.get_widget("look_frame")

        self.treeview_lines_check = self.look_xml.get_widget("treeview_lines_check")

        self.listview_rules_check = self.look_xml.get_widget("listview_rules_check")
        self.use_stock_icons_check = self.look_xml.get_widget("use_stock_icons_check")
        self.use_minitoolbar = self.look_xml.get_widget("use_minitoolbar")

        # icon
        try:
            self.icon = keepnote.gui.get_pixbuf(get_icon_filename(gtk.STOCK_SELECT_COLOR))
        except:
            pass


    def load_options(self, app, notebook):

        self.treeview_lines_check.set_active(app.pref.treeview_lines)
        self.listview_rules_check.set_active(app.pref.listview_rules)
        self.use_stock_icons_check.set_active(app.pref.use_stock_icons)
        self.use_minitoolbar.set_active(app.pref.use_minitoolbar)



    def save_options(self, app):
        
        app.pref.treeview_lines = self.treeview_lines_check.get_active()
        app.pref.listview_rules = self.listview_rules_check.get_active()
        app.pref.use_stock_icons = self.use_stock_icons_check.get_active()
        app.pref.use_minitoolbar = self.use_minitoolbar.get_active()
 


class HelperAppsSection (Section):
    
    def __init__(self, key, dialog, app, label=u"", icon=None):
        Section.__init__(self, key, dialog, app, label, icon)
        
        self.entries = {}
        self.frame = gtk.Frame("")
        self.frame.get_label_widget().set_text("<b>%s</b>" % label)
        self.frame.get_label_widget().set_use_markup(True)
        self.frame.set_property("shadow-type", gtk.SHADOW_NONE)
        
        align = gtk.Alignment()
        align.set_padding(10, 0, 10, 0)
        align.show()
        self.frame.add(align)
        
        self.table = gtk.Table(len(app.pref.external_apps), 2)
        self.table.show()
        align.add(self.table)

        # set icon
        try:
            self.icon = keepnote.gui.get_pixbuf(get_icon_filename(gtk.STOCK_EXECUTE))
        except:
            pass


        
    def load_options(self, app, notebook):

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
    
    def __init__(self, key, dialog, app, label=u"", icon=None):
        Section.__init__(self, key, dialog, app, label, icon)

        self.date_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                   "date_time_frame", keepnote.GETTEXT_DOMAIN)
        self.date_xml.signal_autoconnect(self)
        self.frame = self.date_xml.get_widget("date_time_frame")


    def load_options(self, app, notebook):
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            self.date_xml.get_widget("date_%s_entry" % name).\
                set_text(app.pref.timestamp_formats[name])

    def save_options(self, app):
        # save date formatting
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            app.pref.timestamp_formats[name] = unicode_gtk(
                self.date_xml.get_widget("date_%s_entry" % name).get_text())
        


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



    def load_options(self, app, notebook):

        #self.notebook = notebook

        if self.notebook is not None:
            font = self.notebook.pref.default_font
            family, mods, size = keepnote.gui.richtext.parse_font(font)
            self.notebook_font_family.set_family(family)
            self.notebook_font_size.set_value(size)

            self.notebook_index_dir.set_text(self.notebook.pref.index_dir)


    def save_options(self, app):
        # save notebook font        
        if self.notebook is not None:
            pref = self.notebook.pref
            pref.default_font = "%s %d" % (
                self.notebook_font_family.get_family(),
                self.notebook_font_size.get_value())

            self.notebook.pref.index_dir = \
                self.notebook_index_dir.get_text()

        

class ExtensionsSection (Section):
    
    def __init__(self, key, dialog, app, label=u"", icon=None):
        Section.__init__(self, key, dialog, app, label, icon)
        
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

        self.sw = gtk.ScrolledWindow()
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.sw.set_shadow_type(gtk.SHADOW_IN)
        self.sw.show()
        v.pack_start(self.sw, True, True, 0)

        self.list = gtk.TreeView()
        self.list.show()
        self.sw.add(self.list)


        self.list_store = gtk.ListStore(object, str, str, bool)
        self.list.set_model(self.list_store)

        # enabled column
        column = gtk.TreeViewColumn()
        column.set_title(_("Enabled"))
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self._on_extension_enabled)
        column.pack_start(cell, True)
        column.add_attribute(cell, 'active', 3)
        self.list.append_column(column)
        
        
        # name column
        column = gtk.TreeViewColumn()
        column.set_title(_("Name"))
        cell_text = gtk.CellRendererText()
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 1)
        self.list.append_column(column)

        # description column
        column = gtk.TreeViewColumn()
        column.set_title(_("Description"))
        cell_text = gtk.CellRendererText()
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 2)
        self.list.append_column(column)

        # set icon
        try:
            self.icon = keepnote.gui.get_pixbuf(get_icon_filename(gtk.STOCK_ADD))
        except:
            pass



    def load_options(self, app, notebook):
        
        for ext in app.iter_extensions():
            self.list_store.append([ext, ext.name, ext.description, 
                                    ext.is_enabled()])

        w, h = self.list.size_request()
        w2, h2 = self.sw.get_vscrollbar().size_request()
        self.sw.set_size_request(400, h+w2+10)



    def _on_extension_enabled(self, cell, path):
        """Callback for when enabled check box is clicked"""

        self.list_store[path][3] = not cell.get_active()

    def save_options(self, app):
        
        for row in self.list_store:
            ext, enable = row[0], row[3]
            ext.enable(enable)



#=============================================================================

class ApplicationOptionsDialog (object):
    """Application options"""
    
    def __init__(self, app):
        self.app = app
        self.main_window = None
        self.notebook = None


        self._next_tab_position = 0
        self._sections = []
        self.tree2tab = {}
        
        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "app_options_dialog", keepnote.GETTEXT_DOMAIN)
        self.dialog = self.xml.get_widget("app_options_dialog")
        self.dialog.connect("delete-event", self._on_delete_event)
        self.tabs = self.xml.get_widget("app_options_tabs")
        self.xml.signal_autoconnect({
            "on_cancel_button_clicked": 
                lambda w: self.finish(),
            "on_ok_button_clicked":
                lambda w: self.on_ok_button_clicked()})

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


    def _on_delete_event(self, widget, event):
        """Callback for window close"""

        self.finish()
        self.dialog.stop_emission("delete-event")
        return True

    
    def on_app_options(self, main_window):
        """Display application options"""
        
        self.main_window = main_window
        self.notebook = main_window.get_notebook()
        self.dialog.set_transient_for(main_window)

        # add notebook options
        # TODO: pass notebook at this point
        # TODO: remove notebook reference from load_options/save_options
        self.notebook_sections = [
            self.add_section(NoteBookSection("notebook_%d" % i, 
                                             self.dialog, self.app, 
                                             notebook.get_title(),
                                             notebook), 
                             "notebooks")
            for i, notebook in enumerate(self.app.iter_notebooks())]


        self.load_options(self.app, self.notebook)

        self.dialog.show()


    def add_default_sections(self):

        self.add_section(
            GeneralSection("general", self.dialog, self.app, 
                           keepnote.PROGRAM_NAME))
        self.add_section(
            LookAndFeelSection("look_and_feel", self.dialog, 
                               self.app, _("Look and Feel")), 
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
            Section("notebooks", self.dialog, self.app, 
                    _("Notebook Options"), "folder.png"))
        self.add_section(
            ExtensionsSection("extensions", self.dialog, 
                              self.app, _("Extensions")))

    #=====================================
    # options

    def load_options(self, app, notebook):
        """Load options into sections"""
        
        for section in self._sections:
            section.load_options(self.app, notebook)

    
    def save_options(self, app, notebook):
        """Save the options from each section"""
        
        for section in self._sections:
            section.save_options(self.app)

        # notify application preference changes
        self.app.pref.changed.notify()

        # save noteboook preference changes
        if notebook:
            notebook.write_preferences()
            notebook.notify_change(False)


    #=====================================
    # section handling

    def add_section(self, section, parent=None):
        """Add a section to the Options Dialog"""
        
        # determine parent section
        if parent is not None:
            path = self.get_section_path(parent)
            it = self.overview_store.get_iter(path)
        else:
            it = None

        self._sections.append(section)
        self.tabs.insert_page(section.frame, tab_label=None, 
                              position=self._next_tab_position)
        section.frame.show()
        section.frame.queue_resize()

        icon = section.icon
        if icon is None:
            icon = icon="note.png"
        
        if isinstance(icon, basestring):
            pixbuf = keepnote.gui.get_resource_pixbuf(icon)
        else:
            pixbuf = icon

        # add to overview
        it = self.overview_store.append(it, [section.label, section, pixbuf])
        path = self.overview_store.get_path(it)
        self.overview.expand_to_path(path)
        self.tree2tab[path] = self._next_tab_position

        
        self._next_tab_position += 1

        return section


    def remove_section(self, key):
        
        # TODO: may need to update tree2tab, when other pages slide in position

        path = self.get_section_path(key)

        if path is None:
            return

        # remove from tabs
        pos = self.tree2tab[path]
        self.tabs.remove_page(pos)
        del self.tree2tab[path]

        # remove from tree
        self.overview_store.remove(self.overview_store.get_iter(path))


    def get_section(self, key):
        """Returns the section for a key"""

        for section in self._sections:
            if section.key == key:
                return section

            
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
            self.tabs.set_current_page(self.tree2tab[row])         

    
    def on_ok_button_clicked(self):

        self.save_options(self.app, self.notebook)        

        self.finish()
    

    def finish(self):

        # close dialog
        self.dialog.hide()        

        for section in self.notebook_sections:
            self.remove_section(section.key)


    # TODO: add apply button
    
