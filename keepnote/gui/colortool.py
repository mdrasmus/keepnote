"""

    KeepNote
    Color picker for the toolbar

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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


# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject
import pango

from keepnote.gui import get_resource_image, get_resource_pixbuf


FONT_LETTER = "A"


DEFAULT_COLORS = [
            # lights
            (1, .6, .6),
            (1, .8, .6),
            (1, 1, .6),
            (.6, 1, .6),
            (.6, 1, 1),
            (.6, .6, 1),
            (1, .6, 1),

            # trues
            (1, 0, 0),                    
            (1, .64, 0),
            (1, 1, 0),                    
            (0, 1, 0),
            (0, 1, 1),
            (0, 0, 1),
            (1, 0, 1),

            # darks
            (.5, 0, 0),
            (.5, .32, 0),
            (.5, .5, 0),
            (0, .5, 0),
            (0, .5, .5),
            (0, 0, .5),
            (.5, 0, .5),

            # white, gray, black
            (1, 1, 1),
            (.9, .9, .9),
            (.75, .75, .75),
            (.5, .5, .5),
            (.25, .25, .25),
            (.1, .1, .1),                    
            (0, 0, 0),                    
        ]

# convert to ints
m = 65535
DEFAULT_COLORS = [tuple(int(m*c) for c in color) for color in DEFAULT_COLORS]

# TODO: share the same pallete between color menus



class ColorTextImage (gtk.Image):
    """Image widget that display a color box with and without text"""

    def __init__(self, width, height, letter, border=True):
        gtk.Image.__init__(self)
        self.width = width
        self.height = height
        self.letter = letter
        self.border = border
        self.marginx = int((width - 10) / 2.0)
        self.marginy = - int((height - 12) / 2.0)
        self._pixmap = None
        self._colormap = None
        self.fg_color = None
        self.bg_color = None
        self._exposed = False

        self.connect("parent-set", self.on_parent_set)
        self.connect("expose-event", self.on_expose_event)
        

    def on_parent_set(self, widget, old_parent):
        self._exposed = False
            
        
    def on_expose_event(self, widget, event):
        """Set up colors on exposure"""

        if not self._exposed:
            self._exposed = True
            self.init_colors()


    def init_colors(self):
        self._pixmap = gdk.Pixmap(self.parent.window,
                                  self.width, self.height, -1)
        self.set_from_pixmap(self._pixmap, None)
        self._colormap = self._pixmap.get_colormap()
        #self._colormap = gtk.gdk.colormap_get_system()
        #gtk.gdk.screen_get_default().get_default_colormap()
        self._gc = self._pixmap.new_gc()

        self._context = self.get_pango_context()
        self._fontdesc = pango.FontDescription("sans bold 10")

        if isinstance(self.fg_color, tuple):
            self.fg_color = self._colormap.alloc_color(*self.fg_color)
        elif self.fg_color is None:
            self.fg_color = self._colormap.alloc_color(
                self.get_style().text[gtk.STATE_NORMAL])

        if isinstance(self.bg_color, tuple):
            self.bg_color = self._colormap.alloc_color(*self.bg_color)
        elif self.bg_color is None:
            self.bg_color = self._colormap.alloc_color(
                self.get_style().bg[gtk.STATE_NORMAL])
        
        self._border_color = self._colormap.alloc_color(0, 0, 0)
        self.refresh()


    def set_fg_color(self, red, green, blue, refresh=True):
        """Set the color of the color chooser"""
        if self._colormap:
            self.fg_color = self._colormap.alloc_color(red, green, blue)
            if refresh:
                self.refresh()
        else:
            self.fg_color = (red, green, blue)


    def set_bg_color(self, red, green, blue, refresh=True):
        """Set the color of the color chooser"""
        if self.bg_color:
            self.bg_color = self._colormap.alloc_color(red, green, blue)
            if refresh:
                self.refresh()
        else:
            self.bg_color = (red, green, blue)        
        

    def refresh(self):
        self._gc.foreground = self.bg_color
        self._pixmap.draw_rectangle(self._gc, True, 0, 0,
                                    self.width, self.height)
        if self.border:
            self._gc.foreground = self._border_color
            self._pixmap.draw_rectangle(self._gc, False, 0, 0,
                                        self.width-1, self.height-1)

        if self.letter:
            self._gc.foreground = self.fg_color
            layout = pango.Layout(self._context)
            layout.set_text(FONT_LETTER)
            layout.set_font_description(self._fontdesc)
            self._pixmap.draw_layout(self._gc, self.marginx,
                                     self.marginy,
                                     layout)

        self.set_from_pixmap(self._pixmap, None)



class ColorMenu (gtk.Menu):
    """Color picker menu"""

    def __init__(self, default_colors=DEFAULT_COLORS):
        gtk.Menu.__init__(self)

        self.width = 7
        self.posi = 4
        self.posj = 0

        no_color = gtk.MenuItem("_Default Color")
        no_color.show()
        no_color.connect("activate", self.on_no_color)
        self.attach(no_color, 0, self.width, 0, 1)

        # new color
        new_color = gtk.MenuItem("_New Color...")
        new_color.show()
        new_color.connect("activate", self.on_new_color)
        self.attach(new_color, 0, self.width, 1, 2)

        # grab color
        #new_color = gtk.MenuItem("_Grab Color")
        #new_color.show()
        #new_color.connect("activate", self.on_grab_color)
        #self.attach(new_color, 0, self.width, 2, 3)

        # separator
        item = gtk.SeparatorMenuItem()
        item.show()
        self.attach(item, 0, self.width,  3, 4)

        # default colors
        self.set_default_colors(default_colors)

        # separator
        if self.posj != 0:
            self.posj = 0
            self.posi += 2
        else:
            self.posi += 1
        item = gtk.SeparatorMenuItem()
        item.show()
        self.attach(item, 0, self.width,  self.posi-1, self.posi)
        self.unrealize()
        self.realize()
        


    def set_default_colors(self, colors):
        self.default_colors = list(colors)
        for color in self.default_colors:
            self.append_color(map(int, color))

    def on_new_color(self, menu):
        """Callback for new color"""
        dialog = ColorSelectionDialog("Choose color")

        settings = gtk.settings_get_default()
        #settings.set_property("gtk-color-palette",
        #                     ":".join(["#ff0000"]*50))

        #print dialog.colorsel.get_children()[0].get_children()[1].get_children()[1].get_children()[1]

        response = dialog.run()

        if response == gtk.RESPONSE_OK:                    
            color = dialog.colorsel.get_current_color()
            self.append_color([color.red, color.green, color.blue])
            self.emit("set-color", (color.red, color.green, color.blue))

        dialog.destroy()

    def on_no_color(self, menu):
        """Callback for no color"""
        self.emit("set-color", None)

    def on_grab_color(self, menu):
        pass
        # TODO: complete

    def append_color(self, color):
        self.add_color(self.posi, self.posj,
                       color[0], color[1], color[2])
        self.posj += 1
        if self.posj >= self.width:
            self.posj = 0
            self.posi += 1

    def add_color(self, i, j, r, g, b):                
        self.unrealize()
        
        child = gtk.MenuItem("")
        child.remove(child.child)
        img = ColorTextImage(15, 15, False)                
        img.set_bg_color(r, g, b)
        child.add(img)
        child.child.show()
        child.show()
        child.connect("activate", lambda w: self.emit("set_color",
                                                      (r, g, b)))
        self.attach(child, j, j+1, i, i+1)

        self.realize()

    def clear_custom_colors(self):
        pass


gobject.type_register(ColorMenu)
gobject.signal_new("set-color", ColorMenu, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object,))


class ColorTool (gtk.MenuToolButton):
    """Abstract base class for a ColorTool"""

    def __init__(self, icon, default):
        gtk.MenuToolButton.__init__(self, self.icon, "")
        self.icon = icon
        self.connect("clicked", self.use_color)
        
        self.menu = ColorMenu()
        self.menu.connect("set-color", self.set_color)
        self.set_menu(self.menu)
        
        self.default = default
        self.color = None
        self.default_set = True

        # TODO: make my own menu drop with a smaller drop arrow
        #self.child.get_children()[1].set_image(
        #    get_resource_image("cut.png"))


    def set_color(self, menu, color):
        """Callback from menu"""
        raise Exception("unimplemented")


    def use_color(self, menu):
        self.emit("set-color", self.color)
        

    def set_default(self, color):
        """Set default color"""
        self.default = color
        if self.default_set:
            self.icon.set_fg_color(*self.default)


gobject.type_register(ColorTool)
gobject.signal_new("set-color", ColorTool, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object,))


class FgColorTool (ColorTool):
    """ToolItem for choosing the foreground color"""
    
    def __init__(self, width, height, default):
        self.icon = ColorTextImage(width, height, True, True)
        self.icon.set_fg_color(default[0], default[1], default[2])
        self.icon.set_bg_color(65535, 65535, 65535)
        ColorTool.__init__(self, self.icon, default)


    def set_color(self, menu, color):
        """Callback from menu"""
        if color is None:
            self.default_set = True
            self.icon.set_fg_color(*self.default)
        else:
            self.default_set = False
            self.icon.set_fg_color(color[0], color[1], color[2])

        self.color = color
        self.emit("set-color", color)

 

class BgColorTool (ColorTool):
    """ToolItem for choosing the backgroundground color"""
    
    def __init__(self, width, height, default):
        self.icon = ColorTextImage(width, height, False, True)
        self.icon.set_bg_color(default[0], default[1], default[2])
        ColorTool.__init__(self, self.icon, default)

    
    def set_color(self, menu, color):
        """Callback from menu"""
        if color is None:
            self.default_set = True
            self.icon.set_bg_color(*self.default)
        else:
            self.default_set = False
            self.icon.set_bg_color(color[0], color[1], color[2])

        self.color = color
        self.emit("set-color", color)



class ColorSelectionDialog (gtk.ColorSelectionDialog):

    def __init__(self, title="Choose color"):
        gtk.ColorSelectionDialog.__init__(self, title)
        self.colorsel.set_has_opacity_control(False)

        # hide default gtk pallete
        self.colorsel.set_has_palette(False)

        # structure of ColorSelection widget
        # colorsel = VBox(HBox(selector, VBox(Table, VBox(Label, pallete), 
        #                                     my_pallete)))
        # pallete = Table(Frame(DrawingArea), ...)
        #
        #vbox = self.colorsel.get_children()[0].get_children()[1].get_children()[1]
        #pallete = vbox.get_children()[1]


        vbox = self.colorsel.get_children()[0].get_children()[1]

        # label
        label = gtk.Label(_("Pallete:"))
        label.set_alignment(0, .5)
        label.show()
        vbox.pack_start(label, expand=False, fill=True, padding=0)

        # pallete
        self.pallete = ColorPallete(DEFAULT_COLORS)
        self.pallete.connect("pick-color", self.on_pick_pallete_color)
        self.pallete.show()
        vbox.pack_start(self.pallete, expand=False, fill=True, padding=0)
        
        # pallete buttons
        hbox = gtk.HButtonBox()
        hbox.show()
        vbox.pack_start(hbox, expand=False, fill=True, padding=0)
        
        # new color
        button = gtk.Button("new", stock=gtk.STOCK_NEW)
        button.set_relief(gtk.RELIEF_NONE)
        button.connect("clicked", self.on_new_color)
        button.show()
        hbox.pack_start(button, expand=False, fill=False, padding=0)

        # delete color
        button = gtk.Button("delete", stock=gtk.STOCK_DELETE)
        button.set_relief(gtk.RELIEF_NONE)
        button.connect("clicked", self.on_delete_color)
        button.show()
        hbox.pack_start(button, expand=False, fill=False, padding=0)

        # reset colors
        button = gtk.Button(stock=gtk.STOCK_UNDO)
        button.get_children()[0].get_child().get_children()[1].set_text_with_mnemonic("_Reset")
        button.set_relief(gtk.RELIEF_NONE)
        button.connect("clicked", self.on_reset_colors)
        button.show()
        hbox.pack_start(button, expand=False, fill=False, padding=0)
        

        # colorsel signals
        def func(w):
            color = self.colorsel.get_current_color()
            self.pallete.set_color((color.red, color.green, color.blue))
        self.colorsel.connect("color-changed", func)
                              


    def on_pick_pallete_color(self, widget, color):
        
        self.colorsel.set_current_color(gtk.gdk.Color(* color))


    def on_new_color(self, widget):
        
        color = self.colorsel.get_current_color()
        self.pallete.new_color((color.red, color.green, color.blue))


    def on_delete_color(self, widget):
        
        self.pallete.remove_selected()


    def on_reset_colors(self, widget):
        
        self.pallete.set_colors(DEFAULT_COLORS)



class ColorPallete (gtk.IconView):
    def __init__(self, colors=DEFAULT_COLORS, nrows=1, ncols=7):
        gtk.IconView.__init__(self)
        self._model = gtk.ListStore(gtk.gdk.Pixbuf, object)
        self.colors = []

        self.set_model(self._model)
        self.set_reorderable(True)
        self.set_property("columns", 7)
        self.set_property("spacing", 0)
        self.set_property("column-spacing", 0)
        self.set_property("row-spacing", 0)
        self.set_property("item-padding", 1)
        self.set_property("margin", 1)
        self.set_pixbuf_column(0)

        self.connect("selection-changed", self._on_selection_changed)

        self.set_colors(colors)

        # TODO: could ImageColorText become a DrawingArea widget?
        

    def clear_colors(self):
        self.colors = []
        self._model.clear()


    def set_colors(self, colors):

        self.clear_colors()
        self.colors = list(colors)

        for color in colors:
            self.append_color(color)


    def append_color(self, color):

        width = 30
        height = 20

        # make pixbuf
        pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, width, height)
        self._draw_color(pixbuf, color, 0, 0, width, height)
        
        self._model.append([pixbuf, color])


    def remove_selected(self):
        
        for path in self.get_selected_items():
            self._model.remove(self._model.get_iter(path))


    def new_color(self, color):
        
        self.append_color(color)
        n = self._model.iter_n_children(None)
        self.select_path((n-1,))


    def set_color(self, color):

        width = 30
        height = 20

        it = self._get_selected_iter()
        if it:
            pixbuf = self._model.get_value(it, 0)
            self._draw_color(pixbuf, color, 0, 0, width, height)
            self._model.set_value(it, 1, color)
        pass


    def _get_selected_iter(self):

        for path in self.get_selected_items():
            return self._model.get_iter(path)
        return None
        

    def _on_selection_changed(self, view):

        it = self._get_selected_iter()
        if it:
            color = self._model.get_value(it, 1)
            self.emit("pick-color", color)

        

    def _draw_color(self, pixbuf, color, x, y, width, height):

        border_color = (0, 0, 0)

        # create pixmap
        pixmap = gdk.Pixmap(None, width, height, 24)
        cmap = pixmap.get_colormap()
        gc = pixmap.new_gc()
        color1 = cmap.alloc_color(* color)
        color2 = cmap.alloc_color(* border_color)

        # draw fill
        gc.foreground = color1 #gtk.gdk.Color(* color)
        pixmap.draw_rectangle(gc, True, 0, 0, width, height)
        
        # draw border
        gc.foreground = color2 #gtk.gdk.Color(* border_color)
        pixmap.draw_rectangle(gc, False, 0, 0, width-1, height-1)

        pixbuf.get_from_drawable(pixmap, cmap, 0, 0, 0, 0, width, height)



gobject.type_register(ColorPallete)
gobject.signal_new("pick-color", ColorPallete, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object,))




