"""

    KeepNote
    Import .ncd Extension

"""
#
#  KeepNote
#  Copyright (c) 2008-2010 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@mit.edu>
#  Extension by: Nihil <nihil@blue.dyn-o-saur.com>,
#                Matt Rasmussen <rasmus@mit.edu>
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
import sgmllib
import htmlentitydefs,re
import base64
import string,random

# keepnote imports
import keepnote
import keepnote.gui.extension
from keepnote import notebook as notebooklib
import os,gtk
import pygtk
pygtk.require('2.0')

# unescape html entities
# stolen form
# http://effbot.org/zone/re-sub.htm#unescape-html
# http://www.w3.org/QA/2008/04/unescape-html-entities-python.html
##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text):
   """Removes HTML or XML character references 
      and entities from a text string.
      keep &amp;, &gt;, &lt; in the source code.
   from Fredrik Lundh
   http://effbot.org/zone/re-sub.htm#unescape-html
   """
   def fixup(m):
      text = m.group(0)
      if text[:2] == "&#":
         # character reference
         try:
            if text[:3] == "&#x":
               return unichr(int(text[3:-1], 16))
            else:
               return unichr(int(text[2:-1]))
         except ValueError:
            print "erreur de valeur"
            pass
      else:
         # named entity
         try:
            if text[1:-1] == "amp":
               text = "&amp;amp;"
            elif text[1:-1] == "gt":
               text = "&amp;gt;"
            elif text[1:-1] == "lt":
               text = "&amp;lt;"
            else:
               # print text[1:-1]
               text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
         except KeyError:
            print "keyerror"
            pass
      return text # leave as is
   return re.sub("&#?\w+;", fixup, text)

# http://diveintopython.org/html_processing/index.html
class Extension (keepnote.gui.extension.Extension):
    version = (1, 0)
    name = "Import NoteCase"
    author = "Nihil <nihil@blue.dyn-o-saur.com>"
    website = "http://rasm.ods.org/keepnote/extensions.shtml"
    description = "Primitive import of .ncd Files."

    def __init__(self, app):
        """Initialize extension"""
        
        keepnote.gui.extension.Extension.__init__(self, app)
        self.app = app
        self._action_groups = {}
        self._ui_id = {}


    def on_add_ui(self, window):
        """Initialize extension for a particular window"""
            
        self._action_groups[window] = gtk.ActionGroup("MainWindow")
        self._action_groups[window].add_actions([
            ("Import ncd", None, "Import from .ncd file NoteCase 1.9.8",
             "", None,
             lambda w: self.on_import_ncd(window,
                                          window.get_notebook())),
            ])
        window.get_uimanager().insert_action_group(
           self._action_groups[window], 0)
        
        self._ui_id[window] = window.get_uimanager().add_ui_from_string(
            """
            <ui>
            <menubar name="main_menu_bar">
               <menu action="File">
                  <menu action="Import">
                     <menuitem action="Import ncd"/>
                  </menu>
               </menu>
            </menubar>
            </ui>
            """)

    def on_remove_ui(self, window):        

        # remove option
        window.get_uimanager().remove_action_group(self._action_groups[window])
        del self._action_groups[window]
        
        window.get_uimanager().remove_ui(self._ui_id[window])
        del self._ui_id[window]


    def on_import_ncd(self, window, notebook):
        """Callback from gui for importing an ncd file"""
        
        if notebook is None:
            self.app.error("Must have notebook open to import.")
            return None

        """Imports NoteCase free version ncd file"""
        
        dialog = gtk.FileChooserDialog(
            "import ncd file", None, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN, 
            buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.ncd")
        file_filter.set_name("NoteCase free version 1.9.8(*.ncd)")
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)
        
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            if dialog.get_filename():
                ncd_file = dialog.get_filename()
                if notebook is not None:
                    import_ncd_file(window, ncd_file)
                else:
                    print "WARNING: you need an notebook before you can import"
            # self.close_notebook()
        dialog.destroy()

    

def import_ncd_file(window,file):
    # is this really an .ncd file?
    counter = 10
    fd = open(file,r'r')
    ncd_identified = True #False
    ncd_identifier = r'<meta name="generator" content="NoteCase 1.9.8">'
    while counter>=0:
        pre_data = fd.readline()
        if pre_data[:len(ncd_identifier)] == ncd_identifier:
            ncd_identified = True
        counter -= 1
    fd.close()
    if ncd_identified == False:
        dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK,"Sorry, this is not a data file from the free version of NoteCase")
        dialog.run()
        dialog.destroy()
        return

   # create first node of the imported file
    pos = "sibling"
    nodes, widget = window.get_selected_nodes("treeview")
    if len(nodes) == 1:
        parent = nodes[0]    
    else:
        parent = window.get_notebook()
    if pos == "sibling" and parent.get_parent() is not None:
        index = parent.get_attr("order") + 1
        parent = parent.get_parent()
    else:
        index = None
    node = parent.new_child(notebooklib.CONTENT_TYPE_DIR,notebooklib.DEFAULT_DIR_NAME,index)
    node.rename(unicode(file.split(os.sep)[-1],'utf8'))
    
   # read in file at once
    file_data = ''
    #try:
    fd = open(file,r'r')
    file_data = fd.read()
    fd.close()
    
    myparser = MyParser()
    myparser.parse(file_data,node)
    #except:
    #    pass 

class MyParser(sgmllib.SGMLParser):
    def __init__(self, verbose=1):
        sgmllib.SGMLParser.__init__(self, verbose)
        self.HTML_START = '<html><head></head><body>'
        self.HTML_END= '</body></html>'
        
    def reset(self):
        # extend (called by SGMLParser.__init__)
        self.pieces = []
        self.xtag = None
        self.last_xtag = None
        self.modified_timestamp = "0000000000"
        self.created_timestamp = "0000000000"
        self.node_expanded=False
        sgmllib.SGMLParser.reset(self)
        
    def parse(self,data,node):
        self.node = node
        self.feed(data)
        self.close()
    
    def unknown_starttag(self, tag, attrs):
        if tag != "meta":
            strattrs = "".join([' %s="%s"' % (key, value) for key, value in attrs])
            self.pieces.append("<%(tag)s%(strattrs)s>" % locals())

    def unknown_endtag(self, tag):
        self.pieces.append("</%(tag)s>" % locals())

    def handle_charref(self, ref):  
        # called for each character reference, e.g. for "&#160;", ref will be "160"
        # Reconstruct the original character reference.
        self.pieces.append("&#%(ref)s;" % locals())

    def handle_entityref(self, ref):       
        # called for each entity reference, e.g. for "&copy;", ref will be "copy"
        # Reconstruct the original entity reference.
        self.pieces.append("&%(ref)s" % locals())
        # standard HTML entities are closed with a semicolon; other entities are not
        if htmlentitydefs.entitydefs.has_key(ref):
            self.pieces.append(";")

    def start_img(self, attrs):
        # is this an embedded jpeg?
        sstring = r'data:image/jpeg;base64,'
        if attrs[0][0] == "title" and attrs[1][0] == "src" and attrs[1][1][:len(sstring)] == sstring:
            imagetitle = attrs[0][1]
            imagestr = ""
            imagedata = attrs[1][1][len(sstring):]
            fpath = os.path.dirname(self.node.get_data_file())
            fname = os.path.join(fpath,imagetitle)
            # data is divided into 72 bytes per line ending with \r\n
            while (len(imagedata)>72):
                imagestr += imagedata[:72]
                imagedata = imagedata[74:]
            imagestr += imagedata
            # correct padding for data to be able to decode it
            padder = 4 - len(imagestr) % 4
            padding = padder * "="
            imagestr += padding
            image = base64.b64decode(imagestr)
            fd = open(fname,r'w')
            fd.write(image)
            fd.close()
            # append link into the page
            self.pieces.append('<img src="'+imagetitle+'" >')
        
    def end_img(self):
        pass

    def handle_data(self, text):  
        if text != "\n":
            self.pieces.append(text)

    def handle_comment(self, text):   
        created_str = 'property:date_created='
        modified_str = 'property:date_modified='
        expanded_str = 'property:expanded'
        #self.pieces.append("<!--%(text)s-->" % locals())
        if text[:len(created_str)] == created_str:
            self.created_timestamp = text[len(created_str):len(created_str)+10]
        if text[:len(modified_str)] == modified_str:
            self.modified_timestamp = text[len(modified_str):len(modified_str)+10]
        if text[:len(expanded_str)] == expanded_str:
            self.node_expanded = True

    def handle_pi(self, text):             
        self.pieces.append("<?%(text)s>" % locals())

    def handle_decl(self, text):
        #self.pieces.append("<!%(text)s>" % locals())
        pass

    def start_dl(self, attrs):
        self.last_xtag = self.xtag
        self.xtag = "start_dl"
        if self.last_xtag == "start_dd" and self.xtag == "start_dl" and len(self.pieces) != 0:
            write_node(self.node,self.pieces)
        xnode = self.node.new_child(notebooklib.CONTENT_TYPE_PAGE,notebooklib.DEFAULT_PAGE_NAME)
        xnode.rename(u"anonymous")

    def end_dl(self):
        self.last_xtag = self.xtag
        self.xtag = "end_dl"
        
    def start_dt(self, attrs):
        self.xtag = "start_dt"
        self.pieces = []
        
    def end_dt(self):
        self.last_xtag = self.xtag
        self.xtag = "end_dt"
        child = self.node.get_children()[-1]
        child_name = child.get_attr('title')
        if child_name == 'anonymous':
            xnode = child
        else:
            xnode = self.node.new_child(notebooklib.CONTENT_TYPE_PAGE,notebooklib.DEFAULT_PAGE_NAME)
        # if the environment of the underlying os is set up wrong
        # creating files with utf8 characters will fail
        # we then create the filename with an random name but set the node title correctly
        try:
            xnode.rename(unescape(''.join(self.pieces)))
        except UnicodeEncodeError:
            xnode.rename("".join(random.sample(string.letters+string.digits, 8)))
            xnode.set_attr('title',unescape(''.join(self.pieces)))
        xnode.set_attr('modified_time',int(self.modified_timestamp))
        xnode.set_attr('created_time',int(self.created_timestamp))
        xnode.set_attr('expanded',self.node_expanded)
        self.pieces = []
        self.node_expanded = False
        self.modified_timestamp = "0000000000"
        self.created_timestamp = "0000000000"
        
    def start_dd(self, attrs):
        self.last_xtag = self.xtag
        self.xtag = "start_dd"
        xnode = self.node.get_children()[-1]
        self.node = xnode
        self.pieces = []
        
    def end_dd(self):
        self.last_xtag = self.xtag
        self.xtag = "end_dd"
        if self.xtag == "end_dd" and not self.last_xtag == "end_dl":
            # write data into node
            write_node(self.node,self.pieces)
        xnode = self.node.get_parent()
        self.node = xnode
        self.pieces = []
                
    def output(self):              
        """Return processed HTML as a single string"""
        return "".join(self.pieces)

def write_node(node,data):
    skel1 = '<html><head></head><body>'
    skel2 = '</body></html>' 
    fname = node.get_data_file()
    # why do i need to unescape entities?
    datastring = unescape(''.join(data))
    out = open(fname, "w")
    out.write(skel1+datastring+skel2)
    out.close() 





