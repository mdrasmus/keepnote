"""

    TakeNote
    Image Resize Dialog

"""

# python imports
import os

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade

# takenote imports
import takenote
from takenote import get_resource



class ImageResizeDialog (object):
    """Image Resize dialog """
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.dialog = None
        self.image = None
        self.aspect = True
        self.owidth, self.oheight = None, None
        self.init_width, self.init_height = None, None
        self.ignore_change = False
        
    
    def on_resize(self, image):

        if not image.is_valid():
            self.main_window.error("Cannot resize image that is not properly loaded")
            return
        
        self.xml = gtk.glade.XML(get_resource("rc", "takenote.glade"))    
        self.dialog = self.xml.get_widget("image_resize_dialog")
        self.dialog.set_transient_for(self.main_window)
        self.dialog.connect("response", lambda d, r: self.on_response(r))       
        self.dialog.show()

        self.image = image
        self.aspect = True
        width, height = image.get_size(True)
        self.init_width, self.init_height = width, height
        self.owidth, self.oheight = image.get_original_size()
        
        self.xml.get_widget("width_entry").set_text(str(width))
        self.xml.get_widget("height_entry").set_text(str(height))
        self.xml.get_widget("size_scale").set_value(width)

        self.xml.signal_autoconnect({
            "on_width_entry_changed":
                lambda w: self.on_size_changed("width"),
            "on_height_entry_changed":
                lambda w: self.on_size_changed("height"),
            "on_aspect_check_toggled": 
                lambda w: self.on_aspect_toggled(),
            "on_size_scale_value_changed":
                self.on_scale_value_changed
            })

        


    def get_size(self):
        wstr = self.xml.get_widget("width_entry").get_text()
        hstr = self.xml.get_widget("height_entry").get_text()

        try:
            width, height = int(wstr), int(hstr)

            if width <= 0:
                width = None

            if height <= 0:
                height = None
            
        except ValueError:
            width, height = None, None
        return width, height
        

    def on_response(self, response):
        if response == gtk.RESPONSE_OK:
            width, height = self.get_size()

            if width is not None:
                self.image.scale(width, height)
                self.dialog.destroy()
            else:
                self.main_window.error("Must specify positive integers for image size")
            
        elif response == gtk.RESPONSE_CANCEL:
            self.dialog.destroy()

        elif response == gtk.RESPONSE_APPLY:
            width, height = self.get_size()

            if width is not None:
                self.image.scale(width, height)

        elif response == gtk.RESPONSE_REJECT:
            # restore default image size
                        
            width, height = self.image.get_original_size()
            self.xml.get_widget("width_entry").set_text(str(width))
            self.xml.get_widget("height_entry").set_text(str(height))
            

    def on_size_changed(self, dim):

        
        if self.aspect and not self.ignore_change:
            self.ignore_change = True
            width, height = self.get_size()
            
            if dim == "width" and width is not None:
                height = int(width / float(self.owidth) * self.oheight)
                self.xml.get_widget("size_scale").set_value(width)

                self.xml.get_widget("height_entry").set_text(str(height))

            elif dim == "height" and height is not None:
                width = int(height / float(self.oheight) * self.owidth)
                self.xml.get_widget("width_entry").set_text(str(width))
                
            self.ignore_change = False
        else:
            width, height = self.get_size()

        if width is not None and height is not None:
            self.init_width, self.init_height = width, height
            

    def on_aspect_toggled(self):
        self.aspect = self.xml.get_widget("aspect_check").get_active()
    

    def on_scale_value_changed(self, scale):
        width = int(scale.get_value())
        factor = width / float(self.init_width)
        height = int(factor * self.init_height)

        if not self.ignore_change:
            self.ignore_change = True
            self.xml.get_widget("width_entry").set_text(str(width))
            self.xml.get_widget("height_entry").set_text(str(height))
            self.ignore_change = False
