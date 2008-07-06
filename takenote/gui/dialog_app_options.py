"""

    TakeNote
    Application Options Dialog

"""

# python imports
import os

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk.glade

# takenote imports
import takenote
from takenote import get_resource



class ApplicationOptionsDialog (object):
    """Application options"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.app = main_window.app
        self.entries = {}
    
    def on_app_options(self):
        self.xml = gtk.glade.XML(get_resource("rc", "takenote.glade"))
        self.dialog = self.xml.get_widget("app_config_dialog")
        self.dialog.set_transient_for(self.main_window)


        # populate dialog        
        self.xml.get_widget("default_notebook_entry").\
            set_text(self.app.pref.default_notebook)

        # populate autosave
        self.xml.get_widget("autosave_check").set_active(
            self.app.pref.autosave)
        self.xml.get_widget("autosave_entry").set_text(
            str(int(self.app.pref.autosave_time / 1000)))

        self.xml.get_widget("autosave_entry").set_sensitive(
            self.app.pref.autosave)
        self.xml.get_widget("autosave_label").set_sensitive(
            self.app.pref.autosave)
        

        # populate default font
        #self.xml.get_widget("default_font_button").\
        #    set_font_name(self.app.pref.default_font)

        # populate dates
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            self.xml.get_widget("date_%s_entry" % name).\
                set_text(self.app.pref.timestamp_formats[name])


        # populate external apps
        self.entries = {}
        apps_widget = self.xml.get_widget("external_apps_frame")
        table = gtk.Table(len(self.app.pref.external_apps), 3)
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
                    self.on_app_options_browse(key,
                                               "Choose %s" % title,
                                               prog)
            button = gtk.Button("Browse...")
            button.set_image(
                gtk.image_new_from_stock(gtk.STOCK_OPEN,
                                         gtk.ICON_SIZE_SMALL_TOOLBAR))
            button.show()
            button.connect("clicked", button_clicked(key, app_title, prog))
            table.attach(button, 2, 3, i, i+1,
                         xoptions=0, yoptions=0,
                         xpadding=2, ypadding=2)

        table.show()

        

        self.xml.signal_autoconnect({
            "on_ok_button_clicked": 
                lambda w: self.on_app_options_ok(),
            "on_cancel_button_clicked": 
                lambda w: self.dialog.destroy(),
                
            "on_default_notebook_button_clicked": 
                lambda w: self.on_app_options_browse(
                    "default_notebook", 
                    "Choose Default Notebook",
                    self.app.pref.default_notebook),
            "on_autosave_check_toggled":
                lambda w: self.on_autosave_toggle(w)            
            })

        self.dialog.show()


    def on_autosave_toggle(self, widget):
        self.xml.get_widget("autosave_entry").set_sensitive(
            widget.get_active())
        self.xml.get_widget("autosave_label").set_sensitive(
            widget.get_active())
        
    
    def on_app_options_browse(self, name, title, filename):
        dialog = gtk.FileChooserDialog(title, self.dialog, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Open", gtk.RESPONSE_OK))
        dialog.set_transient_for(self.dialog)
        dialog.set_modal(True)
                
        # set the filename if it is fully specified
        if os.path.isabs(filename):            
            dialog.set_filename(filename)
        
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            dialog.destroy()

            if name == "default_notebook":
                self.xml.get_widget("default_notebook_entry").\
                    set_text(filename)
            else:
                self.entries[name].set_text(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()

    
    def on_app_options_ok(self):
        # TODO: add arguments
    
        self.app.pref.default_notebook = \
            self.xml.get_widget("default_notebook_entry").get_text()

        # save autosave
        self.app.pref.autosave = \
            self.xml.get_widget("autosave_check").get_active()
        try:
            self.app.pref.autosave_time = \
                int(self.xml.get_widget("autosave_entry").get_text()) * 1000
        except:
            pass


        # save date formatting
        for name in ["same_day", "same_month", "same_year", "diff_year"]:
            self.app.pref.timestamp_formats[name] = \
                self.xml.get_widget("date_%s_entry" % name).get_text()
        

        # save external app options
        for key, entry in self.entries.iteritems():
            self.app.pref._external_apps_lookup[key].prog = \
                self.entries[key].get_text()
        
        self.app.pref.write()
        self.app.pref.changed.notify()
        
        self.dialog.destroy()
        self.dialog = None
    
    
