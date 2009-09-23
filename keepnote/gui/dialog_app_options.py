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

# keepnote imports
import keepnote
from keepnote import unicode_gtk
from keepnote import get_resource
from keepnote.gui.font_selector import FontSelector
from keepnote.gui import richtext

_ = gettext.gettext


#class Binding (object):
#    def __init__(self, set=lambda: None, get=lambda: None):
#        self.set = set
#        self.get = get

class OptionsTab (object):
    
    def __init__(self, key, dialog, app):
        self.key = key
        self.dialog = dialog

    def set_options(self, app):
        pass


class GeneralTab (OptionsTab):

    def __init__(self, key, dialog, app):
        OptionsTab.__init__(self, key, dialog, app)
        
        
        
        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                      "general_frame", keepnote.GETTEXT_DOMAIN)
        self.xml.signal_autoconnect(self)
        self.xml.signal_autoconnect({
            "on_default_notebook_button_clicked":
                lambda w: self.on_browse(
                    "default_notebook", 
                    "Choose Default Notebook",
                    app.pref.default_notebook),
            })
        self.frame = self.xml.get_widget("general_frame")


        # populate default notebook        
        if app.pref.use_last_notebook == True:
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

        if self.dialog.main_window.get_notebook():
            self.xml.get_widget("default_notebook_entry").set_text(
                self.dialog.main_window.get_notebook().get_path())
            
        

    def on_browse(self, name, title, filename, 
                  action=gtk.FILE_CHOOSER_ACTION_OPEN):
        """Callback for selecting file browser"""
    
    
        dialog = gtk.FileChooserDialog(title, self.dialog, 
            action=action,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Open"), gtk.RESPONSE_OK))
        dialog.set_transient_for(self.dialog)
        dialog.set_modal(True)
                
        # set the filename if it is fully specified
        if os.path.isabs(filename):            
            dialog.set_filename(filename)
        
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK and dialog.get_filename():
            filename = dialog.get_filename()
            
            self.xml.get_widget("default_notebook_entry").\
                set_text(filename)
            
        dialog.destroy()


    def set_options(self, app):
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


class LookAndFeelTab (OptionsTab):
    
    def __init__(self, key, dialog, app):
        OptionsTab.__init__(self, key, dialog, app)

        self.look_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                      "look_frame", keepnote.GETTEXT_DOMAIN)
        self.look_xml.signal_autoconnect(self)
        self.frame = self.look_xml.get_widget("look_frame")
        self.treeview_lines_check = self.look_xml.get_widget("treeview_lines_check")
        self.treeview_lines_check.set_active(app.pref.treeview_lines)
        self.listview_rules_check = self.look_xml.get_widget("listview_rules_check")
        self.listview_rules_check.set_active(app.pref.listview_rules)
        self.use_stock_icons_check = \
            self.look_xml.get_widget("use_stock_icons_check")
        self.use_stock_icons_check.set_active(app.pref.use_stock_icons)
        self.use_minitoolbar = \
            self.look_xml.get_widget("use_minitoolbar")
        self.use_minitoolbar.set_active(app.pref.use_minitoolbar)


    def set_options(self, app):
        
        app.pref.treeview_lines = self.treeview_lines_check.get_active()
        app.pref.listview_rules = self.listview_rules_check.get_active()
        app.pref.use_stock_icons = self.use_stock_icons_check.get_active()
        app.pref.use_minitoolbar = self.use_minitoolbar.get_active()
 


class HelperAppsTab (OptionsTab):
    
    def __init__(self, key, dialog, app):
        OptionsTab.__init__(self, key, dialog, app)
        
        self.entries = {}
        apps_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "helper_apps_frame", keepnote.GETTEXT_DOMAIN)
        apps_xml.signal_autoconnect(self)
        self.frame = apps_xml.get_widget("helper_apps_frame")

        apps_widget = apps_xml.get_widget("external_apps_frame")
        table = gtk.Table(len(app.pref.external_apps), 2)
        apps_widget.add_with_viewport(table)
        apps_widget.get_child().set_property("shadow-type", gtk.SHADOW_NONE)
        
        for i, app in enumerate(app.pref.external_apps):
            key = app.key
            app_title = app.title
            prog = app.prog
            
            # program label
            label = gtk.Label(app_title +":")
            label.set_justify(gtk.JUSTIFY_RIGHT)
            label.set_alignment(1.0, 0.5)
            label.show()
            table.attach(label, 0, 1, i, i+1,
                         xoptions=gtk.FILL, yoptions=0,
                         xpadding=2, ypadding=2)

            # program entry
            entry = gtk.Entry()
            entry.set_text(prog)
            entry.show()
            self.entries[key] = entry
            table.attach(entry, 1, 2, i, i+1,
                         xoptions=gtk.FILL | gtk.EXPAND, yoptions=0,
                         xpadding=2, ypadding=2)

            # browse button
            def button_clicked(key, title, prog):
                return lambda w: \
                    self.on_browse(key,
                                   _("Choose %s") % title,
                                   prog)
            button = gtk.Button(_("Browse..."))
            button.set_image(
                gtk.image_new_from_stock(gtk.STOCK_OPEN,
                                         gtk.ICON_SIZE_SMALL_TOOLBAR))
            button.show()
            button.connect("clicked", button_clicked(key, app_title, prog))
            table.attach(button, 2, 3, i, i+1,
                         xoptions=0, yoptions=0,
                         xpadding=2, ypadding=2)

        table.show()


    def on_browse(self, name, title, filename, 
                  action=gtk.FILE_CHOOSER_ACTION_OPEN):
        """Callback for selecting file browser"""
    
    
        dialog = gtk.FileChooserDialog(title, self.dialog, 
            action=action,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Open"), gtk.RESPONSE_OK))
        dialog.set_transient_for(self.dialog)
        dialog.set_modal(True)
                
        # set the filename if it is fully specified
        if os.path.isabs(filename):            
            dialog.set_filename(filename)
        
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK and dialog.get_filename():
            filename = dialog.get_filename()
            self.entries[name].set_text(filename)
            
        dialog.destroy()  

    def set_options(self, app):

        # save external app options
        for key, entry in self.entries.iteritems():
            if key in app.pref._external_apps_lookup:
                app.pref._external_apps_lookup[key].prog = unicode_gtk(
                    self.entries[key].get_text())



class DatesTab (OptionsTab):
    
    def __init__(self, key, dialog, app):
        OptionsTab.__init__(self, key, dialog, app)

        self.date_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                   "date_time_frame", keepnote.GETTEXT_DOMAIN)
        self.date_xml.signal_autoconnect(self)
        self.frame = self.date_xml.get_widget("date_time_frame")
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            self.date_xml.get_widget("date_%s_entry" % name).\
                set_text(app.pref.timestamp_formats[name])

    def set_options(self, app):
        # save date formatting
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            app.pref.timestamp_formats[name] = unicode_gtk(
                self.date_xml.get_widget("date_%s_entry" % name).get_text())
        


class NoteBookTab (OptionsTab):
    
    def __init__(self, key, dialog, app, notebook):
        OptionsTab.__init__(self, key, dialog, app)
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
        self.entries["index_dir"] = self.notebook_index_dir
        self.notebook_xml.get_widget("index_dir_browse").connect(
            "clicked",
            lambda w: self.on_browse(
                "index_dir",
                _("Choose alternative notebook index directory"),
                "", action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER))

        if self.notebook is not None:
            font = self.notebook.pref.default_font
            family, mods, size = richtext.parse_font(font)
            self.notebook_font_family.set_family(family)
            self.notebook_font_size.set_value(size)

            self.notebook_index_dir.set_text(self.notebook.pref.index_dir)

    def on_browse(self, name, title, filename, 
                  action=gtk.FILE_CHOOSER_ACTION_OPEN):
        """Callback for selecting file browser"""
    
    
        dialog = gtk.FileChooserDialog(title, self.dialog, 
            action=action,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Open"), gtk.RESPONSE_OK))
        dialog.set_transient_for(self.dialog)
        dialog.set_modal(True)
                
        # set the filename if it is fully specified
        if os.path.isabs(filename):            
            dialog.set_filename(filename)
        
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK and dialog.get_filename():
            filename = dialog.get_filename()
            self.entries[name].set_text(filename)
            
        dialog.destroy()  



    def set_options(self, app):
        # save notebook font        
        if self.notebook is not None:
            pref = self.notebook.pref
            pref.default_font = "%s %d" % (
                self.notebook_font_family.get_family(),
                self.notebook_font_size.get_value())

            self.notebook.pref.index_dir = \
                self.notebook_index_dir.get_text()

            self.notebook.write_preferences()
            self.notebook.notify_change(False)
        



class ApplicationOptionsDialog (object):
    """Application options"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.app = main_window.app
        self.entries = {}
        self.tree2tab = {}
        self._sections = []

    
    def on_app_options(self):
        """Display application options"""
        
        self._next_tab_position = 0
        
        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "app_options_dialog", keepnote.GETTEXT_DOMAIN)
        self.dialog = self.xml.get_widget("app_options_dialog")
        self.dialog.set_transient_for(self.main_window)
        self.tabs = self.xml.get_widget("app_options_tabs")
        self.xml.signal_autoconnect(self)
        self.xml.signal_autoconnect({
            "on_cancel_button_clicked": 
                lambda w: self.dialog.destroy()})

        # setup treeview
        self.overview = self.xml.get_widget("app_config_treeview")
        self.overview_store = gtk.TreeStore(str, object)
        self.overview.set_model(self.overview_store)
        self.overview.connect("cursor-changed", self.on_overview_select)
        #self.set_headers_visible(False)

        # create the treeview column
        column = gtk.TreeViewColumn()
        self.overview.append_column(column)
        cell_text = gtk.CellRendererText()
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 0)

        # add tabs
        self.add_default_sections()

        self.dialog.show()


    def add_section(self, section, name, parent=None):
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

        it = self.overview_store.append(it, [name, section])
        path = self.overview_store.get_path(it)
        self.overview.expand_to_path(path)
        self.tree2tab[path] = self._next_tab_position
        self._next_tab_position += 1


    def get_section(self, key):
        """Returns the section for a key"""

        for section in self._sections:
            if section.key == key:
                return section

            
    def get_section_path(self, section):
        """Returns the TreeModel path for a section"""

        for row in self.overview_store:
            if row[1] == section:
                return row.path

        return None


    def add_default_sections(self):
        
        general_tab = GeneralTab("general", self.dialog, self.app)
        self.add_section(general_tab, keepnote.PROGRAM_NAME)

        look_tab = LookAndFeelTab("look_and_feel", self.dialog, self.app)
        self.add_section(look_tab, _("Look and Feel"), general_tab)

        
        helper_tab = HelperAppsTab("helper_apps", self.dialog, self.app)
        self.add_section(helper_tab, _("Helper Applications"), general_tab)

        dates_tab = DatesTab("date_and_time", self.dialog, self.app)
        self.add_section(dates_tab, _("Date and Time"), general_tab)

        notebook_tab = NoteBookTab("notebook", self.dialog, self.app, 
                                        self.main_window.get_notebook())
        self.add_section(notebook_tab, _("This Notebook"))



    def on_overview_select(self, overview):
        """Callback for changing topic in overview"""
        
        row, col = overview.get_cursor()
        if row is not None:
            self.tabs.set_current_page(self.tree2tab[row])         

    
    def on_ok_button_clicked(self, widget):

        # set the options from each section
        for section in self._sections:
            section.set_options(self.app)
        
        # notify application preference changes
        self.app.pref.changed.notify()
        
        # close dialog
        self.dialog.destroy()
        self.dialog = None
    
    
