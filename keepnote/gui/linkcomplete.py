
# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk
import gobject

# keepnote imports
from keepnote import unicode_gtk
from keepnote.gui.popupwindow import PopupWindow
    

class LinkPicker (gtk.TreeView):

    def __init__(self, maxwidth=450):
        gtk.TreeView.__init__(self)
        self._maxwidth = maxwidth

        self.set_headers_visible(False)

        # add column
        self.column = gtk.TreeViewColumn()
        self.append_column(self.column)

        # create a cell renderers
        self.cell_icon = gtk.CellRendererPixbuf()
        self.cell_text = gtk.CellRendererText()

        # add the cells to column
        self.column.pack_start(self.cell_icon, False)
        self.column.pack_start(self.cell_text, True)

        # map cells to columns in treestore
        self.column.add_attribute(self.cell_icon, 'pixbuf', 0)
        self.column.add_attribute(self.cell_text, 'text', 1)

        self.list = gtk.ListStore(gtk.gdk.Pixbuf, str, object)
        self.set_model(self.list)
        
        self.maxlinks = 10

        


    def set_links(self, urls):

        self.list.clear()
        for nodeid, url, icon in urls[:self.maxlinks]:
            self.list.append([icon, url, nodeid])

        self.column.queue_resize()

        w, h = self.size_request()
        if w > self._maxwidth:
            self.set_size_request(self._maxwidth, -1)
        else:
            self.set_size_request(-1, -1)



class LinkPickerPopup (PopupWindow):

    def __init__(self, parent, maxwidth=100):
        PopupWindow.__init__(self, parent)
        self._maxwidth = maxwidth
        
        self._link_picker = LinkPicker()
        self._link_picker.show()
        self._link_picker.get_selection().connect("changed", self.on_select_changed)
        self._cursor_move = False

        self._shown = False

        # use frame for border
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        frame.add(self._link_picker)
        frame.show()
        self.add(frame)
       

    def set_links(self, urls):
        """Set links in popup"""
        self._link_picker.set_links(urls)

        if len(urls) == 0:
            self.hide()
            self._shown = False
        else:
            self.show()
            self._shown = True


            
    def shown(self):
        """Return True if popup is visible"""
        return self._shown


    def on_key_press_event(self, widget, event):
        """Callback for key press events"""

        model, sel = self._link_picker.get_selection().get_selected()
        
        if event.keyval == gtk.keysyms.Down:            
            # move selection down
            self._cursor_move = True

            if sel is None:
                self._link_picker.set_cursor((0,))
            else:
                i = model.get_path(sel)[0]
                n = model.iter_n_children(None)
                if i < n - 1:
                    self._link_picker.set_cursor((i+1,))

            return True

        elif event.keyval == gtk.keysyms.Up:
            # move selection up            
            self._cursor_move = True

            if sel is None:
                n = model.iter_n_children(None)
                self._link_picker.set_cursor((n-1,))
            else:
                i = model.get_path(sel)[0]
                if i > 0:
                    self._link_picker.set_cursor((i-1,))

            return True

        elif event.keyval == gtk.keysyms.Return:
            # accept selection
            if sel:
                icon, title, nodeid = model[sel]
                self.emit("pick-link", unicode_gtk(title), nodeid)
                return True

        elif event.keyval == gtk.keysyms.Escape:
            # discard popup
            self.set_links([])


        return False



    def on_select_changed(self, treeselect):
        
        if not self._cursor_move:
            model, sel = self._link_picker.get_selection().get_selected()
            if sel:
                icon, title, nodeid = model[sel]
                self.emit("pick-link", unicode_gtk(title), nodeid)
        
        self._cursor_move = False

        #model, paths = treeselect.get_selected_rows()
        #self.__sel_nodes = [self.model.get_value(self.model.get_iter(path),
        #                                         self._node_col)
        #                    for path in paths]
        


gobject.type_register(LinkPickerPopup)
gobject.signal_new("pick-link", LinkPickerPopup, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (str, object))


