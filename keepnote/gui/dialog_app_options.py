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
from keepnote import get_resource
from keepnote.gui.font_selector import FontSelector
from keepnote.gui import richtext

_ = gettext.gettext


#class Binding (object):
#    def __init__(self, set=lambda: None, get=lambda: None):
#        self.set = set
#        self.get = get



class ApplicationOptionsDialog (object):
    """Application options"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.app = main_window.app
        self.entries = {}
        
    
    def on_app_options(self):
        """Display application options"""

        self.bindings = []
        
        
        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "app_options_dialog", keepnote.GETTEXT_DOMAIN)
        self.dialog = self.xml.get_widget("app_options_dialog")
        self.dialog.set_transient_for(self.main_window)
        self.tabs = self.xml.get_widget("app_options_tabs")
        self.setup_overview_tree()
        self.xml.signal_autoconnect(self)
        self.xml.signal_autoconnect({
            "on_cancel_button_clicked": 
                lambda w: self.dialog.destroy()})


        #===================================
        # setup general tab
        self.general_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                      "general_frame", keepnote.GETTEXT_DOMAIN)
        self.general_xml.signal_autoconnect(self)
        self.general_xml.signal_autoconnect({
            "on_default_notebook_button_clicked":
                lambda w: self.on_browse(
                    "default_notebook", 
                    "Choose Default Notebook",
                    self.app.pref.default_notebook),
            })
        frame = self.general_xml.get_widget("general_frame")
        self.tabs.insert_page(frame, tab_label=None, position=0)

        
        # populate default notebook        
        if self.app.pref.use_last_notebook == True:
            self.general_xml.get_widget("last_notebook_radio").set_active(True)
        elif self.app.pref.default_notebook == "":
            self.general_xml.get_widget("no_default_notebook_radio").set_active(True)
        else:
            self.general_xml.get_widget("default_notebook_radio").set_active(True)
            self.general_xml.get_widget("default_notebook_entry").\
                set_text(self.app.pref.default_notebook)
            


        # populate autosave
        self.general_xml.get_widget("autosave_check").set_active(
            self.app.pref.autosave)
        self.general_xml.get_widget("autosave_entry").set_text(
            str(int(self.app.pref.autosave_time / 1000)))

        self.general_xml.get_widget("autosave_entry").set_sensitive(
            self.app.pref.autosave)
        self.general_xml.get_widget("autosave_label").set_sensitive(
            self.app.pref.autosave)
        

        # use systray icon
        self.general_xml.get_widget("systray_check").set_active(self.app.pref.use_systray)
        self.general_xml.get_widget("skip_taskbar_check").set_active(self.app.pref.skip_taskbar)
        self.general_xml.get_widget("skip_taskbar_check").set_sensitive(self.app.pref.use_systray)
        
        
        #====================================
        # look and feel
        self.look_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "look_frame", keepnote.GETTEXT_DOMAIN)
        self.look_xml.signal_autoconnect(self)
        frame = self.look_xml.get_widget("look_frame")
        self.tabs.insert_page(frame, tab_label=None, position=1)
        self.treeview_lines_check = self.look_xml.get_widget("treeview_lines_check")
        self.treeview_lines_check.set_active(self.app.pref.treeview_lines)
        self.listview_rules_check = self.look_xml.get_widget("listview_rules_check")
        self.listview_rules_check.set_active(self.app.pref.listview_rules)
        self.use_stock_icons_check = \
            self.look_xml.get_widget("use_stock_icons_check")
        self.use_stock_icons_check.set_active(self.app.pref.use_stock_icons)


        #======================================
        # populate external apps
        self.entries = {}
        self.apps_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "helper_apps_frame", keepnote.GETTEXT_DOMAIN)
        self.apps_xml.signal_autoconnect(self)
        frame = self.apps_xml.get_widget("helper_apps_frame")
        self.tabs.insert_page(frame, tab_label=None, position=2)
        apps_widget = self.apps_xml.get_widget("external_apps_frame")
        table = gtk.Table(len(self.app.pref.external_apps), 2)
        apps_widget.add_with_viewport(table)
        apps_widget.get_child().set_property("shadow-type", gtk.SHADOW_NONE)
        
        for i, app in enumerate(self.app.pref.external_apps):
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

        #=============================
        # populate dates
        self.date_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "date_time_frame", keepnote.GETTEXT_DOMAIN)
        self.date_xml.signal_autoconnect(self)
        frame = self.date_xml.get_widget("date_time_frame")
        self.tabs.insert_page(frame, tab_label=None, position=3)
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            self.date_xml.get_widget("date_%s_entry" % name).\
                set_text(self.app.pref.timestamp_formats[name])



        #===============================
        # add notebook font widget
        self.notebook_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "notebook_frame", keepnote.GETTEXT_DOMAIN)
        self.notebook_xml.signal_autoconnect(self)
        frame = self.notebook_xml.get_widget("notebook_frame")
        self.tabs.insert_page(frame, tab_label=None, position=4)
        notebook_font_spot = self.notebook_xml.get_widget("notebook_font_spot")
        self.notebook_font_family = FontSelector()
        notebook_font_spot.add(self.notebook_font_family)
        self.notebook_font_family.show()        

        # populate notebook font
        self.notebook_font_size = self.notebook_xml.get_widget("notebook_font_size")
        self.notebook_font_size.set_value(10)

        if self.main_window.notebook is not None:
            font = self.main_window.notebook.pref.default_font
            family, mods, size = richtext.parse_font(font)
            self.notebook_font_family.set_family(family)
            self.notebook_font_size.set_value(size)


        self.dialog.show()



    def setup_overview_tree(self):

        # setup treeview
        self.overview = self.xml.get_widget("app_config_treeview")
        overview_store = gtk.TreeStore(str)
        self.overview.set_model(overview_store)
        self.overview.connect("cursor-changed", self.on_overview_select)
        #self.set_headers_visible(False)

        # create the treeview column
        column = gtk.TreeViewColumn()
        self.overview.append_column(column)
        cell_text = gtk.CellRendererText()
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 0)

        # populate treestore
        app = overview_store.append(None, [keepnote.PROGRAM_NAME])
        overview_store.append(app, [_("Look and Feel")])
        overview_store.append(app, [_("Helper Applications")])
        overview_store.append(app, [_("Date and Time")])
        note = overview_store.append(None, [_("This Notebook")])

        self.overview.expand_all()

        self.tree2tab = {
            (0,): 0,
            (0, 0,): 1,            
            (0, 1,): 2,
            (0, 2,): 3,
            (1,): 4
            }
        

    def on_overview_select(self, overview):
        """Callback for changing topic in overview"""
        
        row, col = overview.get_cursor()
        if row is not None:
            self.tabs.set_current_page(self.tree2tab[row])


    def on_autosave_check_toggled(self, widget):
        """The autosave option controls sensitivity of autosave time"""
        self.general_xml.get_widget("autosave_entry").set_sensitive(
            widget.get_active())
        self.general_xml.get_widget("autosave_label").set_sensitive(
            widget.get_active())


    def on_systray_check_toggled(self, widget):
        """Systray option controls sensitivity of skip taskbar"""
        self.general_xml.get_widget("skip_taskbar_check").set_sensitive(
            widget.get_active())
        
    
    def on_browse(self, name, title, filename):
        """Callback for selecting file browser"""
    
    
        dialog = gtk.FileChooserDialog(title, self.dialog, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Open"), gtk.RESPONSE_OK))
        dialog.set_transient_for(self.dialog)
        dialog.set_modal(True)
                
        # set the filename if it is fully specified
        if os.path.isabs(filename):            
            dialog.set_filename(filename)
        
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()

            if name == "default_notebook":
                self.general_xml.get_widget("default_notebook_entry").\
                    set_text(filename)
            else:
                self.entries[name].set_text(filename)
            
        dialog.destroy()


    def on_set_default_notebook_button_clicked(self, widget):

        if self.main_window.notebook:
            self.general_xml.get_widget("default_notebook_entry").set_text(
                self.main_window.notebook.get_path())
            
        

    def on_default_notebook_radio_changed(self, radio):
        """Default notebook radio changed"""

        no_default = self.general_xml.get_widget("no_default_notebook_radio")
        default = self.general_xml.get_widget("default_notebook_radio")
        last = self.general_xml.get_widget("last_notebook_radio")

        default_tab = self.general_xml.get_widget("default_notebook_table")
        default_tab.set_sensitive(default.get_active())
            


    
    def on_ok_button_clicked(self, widget):
        # TODO: add arguments
    

        if self.general_xml.get_widget("last_notebook_radio").get_active():
            self.app.pref.use_last_notebook = True
        elif self.general_xml.get_widget("default_notebook_radio").get_active():
            self.app.pref.use_last_notebook = False
            self.app.pref.default_notebook = \
                self.general_xml.get_widget("default_notebook_entry").get_text()
        else:
            self.app.pref.use_last_notebook = False
            self.app.pref.default_notebook = ""


        # save autosave
        self.app.pref.autosave = \
            self.general_xml.get_widget("autosave_check").get_active()
        try:
            self.app.pref.autosave_time = \
                int(self.general_xml.get_widget("autosave_entry").get_text()) * 1000
        except:
            pass

        # use systray icon
        self.app.pref.use_systray = self.general_xml.get_widget("systray_check").get_active()
        self.app.pref.skip_taskbar = self.general_xml.get_widget("skip_taskbar_check").get_active()

        # look and feel
        self.app.pref.treeview_lines = self.treeview_lines_check.get_active()
        self.app.pref.listview_rules = self.listview_rules_check.get_active()
        self.app.pref.use_stock_icons = self.use_stock_icons_check.get_active()
        
        
        # save date formatting
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            self.app.pref.timestamp_formats[name] = \
                self.date_xml.get_widget("date_%s_entry" % name).get_text()
        

        # save external app options
        for key, entry in self.entries.iteritems():
            self.app.pref._external_apps_lookup[key].prog = \
                self.entries[key].get_text()

        # save notebook font        
        if self.main_window.notebook is not None:
            pref = self.main_window.notebook.pref
            pref.default_font = "%s %d" % (
                self.notebook_font_family.get_family(),
                self.notebook_font_size.get_value())

            # TODO: move this out.  Use signals to envoke save
            self.main_window.notebook.write_preferences()
            self.main_window.notebook.notify_change(False)
            
        
        self.app.pref.write()
        self.app.pref.changed.notify()

        
        self.dialog.destroy()
        self.dialog = None
    
    
