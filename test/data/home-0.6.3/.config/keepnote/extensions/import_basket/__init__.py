# -*- coding: utf-8 -*-
"""

    KeepNote
    Import Basket Notepad Extension

"""
#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Nihil <nihil@blue.dyn-o-saur.com>,Matt Rasmussen <rasmus@mit.edu>
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
# CHANGELOG
# 4 July 2010
# Version 0.5 initial release
# 28 July 2010
# Version 0.6 improved Basket HTML --> Keepnote HTML transformation



import keepnote
import keepnote.gui.extension
from keepnote import notebook as notebooklib
from keepnote import tasklib
import os,gtk
import pygtk
pygtk.require('2.0')

#from xml.dom.ext.reader import HtmlLib
import shutil
import sgmllib
import htmlentitydefs,re
import base64
import string,random
import glob
import HTMLParser
import codecs
import locale
import sys

import unicodedata

def strip_accents(str):
    """
        remove all non ascii characters from a string
    """
    nkfd_form = unicodedata.normalize('NFKD', unicode(str))
    only_ascii = nkfd_form.encode('ASCII', 'ignore')
    return only_ascii

try:
    # Python version >= 2.5
    from xml.etree import ElementTree
    from xml.etree.ElementTree import XML, fromstring, tostring
    import xml.etree.ElementTree as ET # Python 2.5
except ImportError, e:
    # Python version < 2.5
    from elementtree import ElementTree
    from elementtree.ElementTree import XML, fromstring, tostring
    import elementtree.ElementTree as ET



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
    name = "Import Basket"
    author = "Corrado"
    website = "http://www.gmail.com"
    description = "Primitive import of Basket Notepad Databases."

    def __init__(self, app):
        """Initialize extension"""
        
        keepnote.gui.extension.Extension.__init__(self, app)
        self.app = app
        self._ui_id = {}


    def on_add_ui(self, window):
        """Initialize extension for a particular window"""
            
        self.action_group = gtk.ActionGroup("MainWindow")
        self.action_group.add_actions([
            ("Import BasketNotepad", None, "Import from Basket Directory",
             "", None,
             lambda w: self.on_import_basket(window,
                                          window.get_notebook())),
            ])
        window.get_uimanager().insert_action_group(self.action_group, 0)
        
        self._ui_id[window] = window.get_uimanager().add_ui_from_string(
            """
            <ui>
            <menubar name="main_menu_bar">
               <menu action="File">
                  <menu action="Import">
                     <menuitem action="Import BasketNotepad"/>
                  </menu>
               </menu>
            </menubar>
            </ui>
            """)

            
    def on_remove_ui(self, window):        

        # remove option
        window.get_uimanager().remove_action_group(self.action_group)
        self.action_group = None
        
        window.get_uimanager().remove_ui(self._ui_id[window])
        del self._ui_id[window]


    def on_import_basket(self, window, notebook):
        """Callback from gui for importing a Basket Notepad Directory"""
        
        if notebook is None:
            self.app.error("Must have notebook open to import.")
            return None

        """Imports Basket Notepad Directory Database"""
        
        basket_dir = os.path.expanduser('~')+os.sep+".kde/share/apps/basket"
        import_basket_directory(window, basket_dir+"/baskets")
  

def import_basket_directory(window, basket_directory):
    # is this really a Basket Notepad Directory?
    counter = 10
    basket_xml_file = basket_directory + os.sep + "baskets.xml"
    try:
        fd = open(basket_xml_file, r'r')
    except IOError, e:
        errno, strerror = e
        print "I/O error(%s): %s" % (errno, strerror)
        dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK, "Sorry, this is not a data directory of Basket Notepad, baskets.xml not found!")
        dialog.run()
        dialog.destroy()
        return
    basket_identified = True #False
    basket_identifier = r'<!DOCTYPE basketTree>'
    while counter>=0:
        pre_data = fd.readline()
        if pre_data[:len(basket_identifier)] == basket_identifier:
            basket_identified = True
        counter -= 1
    fd.close()
    if basket_identified == False:
        dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_OK, "Sorry, this is not a data directory of Basket Notepad!")
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
    rootKeepNoteNode = parent.new_child(notebooklib.CONTENT_TYPE_DIR, notebooklib.DEFAULT_DIR_NAME, index)
    rootKeepNoteNode.rename(unicode("Basket Notepad",'utf8'))
    
    BasketIndexParser.import_basket(basket_xml_file, rootKeepNoteNode, basket_directory, window)

class BasketIndexParser():
    """ A Basket notepad index file parser:  ~/.kde/share/apps/basket/baskets/baskets.xml
        For each basket node will create a Keepnote node,
        a basket node can contains many notes(each of them is saved into a note*.html),
        in that case all note*.html are merged in a unique keepnote page.html
    """
        
    def reset(self):
        self.modified_timestamp = "0000000000"
        self.created_timestamp = "0000000000"
        self.node_expanded=False
        
    def parse(self, basketTreeNode, rootKeepNoteNode, basket_directory, window):
        self.notebook = window.get_notebook()
        self.basket_directory = basket_directory
        self.file_count = 0
        for root, dirs, files in os.walk(basket_directory):
            for file in files:    
                if file.endswith('.html'):
                    self.file_count += 1
        self.fc = 0
        self.visitBasketTree(basketTreeNode, rootKeepNoteNode, basket_directory, window)

    def visitBasketTree(self, basketTreeNode, keepNoteNode, basket_directory, window):
        for basketNode in basketTreeNode:
            name, folderName, icon, isLeaf = self.visitBasket(basketNode, keepNoteNode, basket_directory, window)

    def visitBasket(self, basketNode, keepNoteNode, basket_directory, window):
        """
            Returns the number of children <basket> tags, 
            if such number is zero, the node is considered a "leaf" of the tree
        """
        basketTagCount = 0
        for nd in basketNode:
            # This cycle is used to see if the current node is a Folder or a Leaf of the tree:
            if nd.tag == 'basket':
                basketTagCount += 1
        isLeaf = (basketTagCount == 0)
        name, icon = self.getBasketInfo(basketNode)
        folderName = basketNode.attrib["folderName"]
        #print ("Node Name: %s, Folder Name: %s, Icon: %s, isLeaf: %s"%(name, folderName, icon, isLeaf)).encode('utf-8')

        childKeepNoteNode  = self.createKeepNoteNode(keepNoteNode, name, folderName, icon, isLeaf)

        for nd in basketNode:
            if nd.tag == 'basket':
                # A child <basket> has been found: it has to be visited
                name, folderName, icon, isLeaf = self.visitBasket(nd, childKeepNoteNode, basket_directory, window)

        return (name, folderName, icon, isLeaf)

    def getBasketInfo(self, basketNode):
        """
            Can be called only on a <basket> node
            Returns the node name and the node icon file
        """
        properties = None
        name = None
        icon = None
        for ndp in basketNode:
            # Search for a child <properties> tag inside the <basket> tag
            if ndp.tag == 'properties':
                properties = ndp
                for ndn in properties:
                    # Search for a child <name> or <icon> tag inside the <properties> tag
                    if ndn.tag == 'name':
                        name = ndn.text
                    elif ndn.tag == 'icon':
                        icon = ndn.text
                        if icon[0] != '/':
                            icon = None
                break;

        return (name, icon)                    


    def createKeepNoteNode(self, parentNode, name, folderName, icon, isLeaf):
        """
            - create a new Keepnote node
        """
           
        xnode = parentNode.new_child(notebooklib.CONTENT_TYPE_PAGE, notebooklib.DEFAULT_PAGE_NAME)
        xnode.set_attr('expanded', False)
        xnode.set_attr('expanded2', False)
                
        html_content = self.getMergedHTMLFromBaskets(folderName, xnode.get_data_file())                           
        
        # Set the icon for the new keepnote node
        if  icon:
            basename = os.path.basename(icon)
            basename, ext = os.path.splitext(basename)
            # lookup in notebook icon store
            if self.notebook is not None:
                icon_file = self.notebook.get_icon_file(basename)
                if not icon_file:
                    icon_file = self.install_icon(icon)
                xnode.set_attr("icon", icon_file)

        # Write text for the new keepnote node into the associated file
        if html_content:
            write_node(xnode, html_content)        


        # if the environment of the underlying os is set up wrong
        # creating files with utf8 characters will fail
        # we then create the filename with an random name but set the node title correctly
        if type(name) is not unicode:
            try:
                name = unicode(name, "utf-8")
                #xnode.rename(name)
            except UnicodeEncodeError:
                name = unicode(name, "latin-1")
                #xnode.rename("".join(random.sample(string.letters+string.digits, 8)))
                #xnode.set_attr('title',unescape(name))
        nname = strip_accents(name)
        if nname != name:
            print "oldname: %s newname: %s"%(repr(name),nname)
        xnode.rename(nname)
        return xnode

    def getMergedHTMLFromBaskets(self, folderName, data_file):
        """
            Returns an HTML text result of merging all notes inside the basket whose folder is "folderName"
        """
        # List the HTML and image files contained into the basket note directory:
        basket_node_directory = os.path.join(self.basket_directory, folderName)
        # Retrieve the order of note*.html, .png, .gif, .jpg files inside the basket note node
        # files: an ordered list of note*.html, .png, .gif, .jpg files
        # links: and ordered list of links contained into the basket note node
        (files, links) = BasketNodeDescParser.get_nodes_order(basket_node_directory)
        html_content = ""
        for fl in files:
            # This iteration respects the original order of note*.html and images files contained into the basket note node
            fname = os.path.join(basket_node_directory, fl)
            if fl.lower().endswith("html"):
                # read the HTML file and remove the <html><head> and <style> tags
                html_content += read_html_file(fname) + "<HR></HR>"
                self.fc += 1
                # print "Read %d/%d files"%(self.fc,self.file_count)
            else:
                # create an image HTML tag and copy the image into the Keepnote note node folder
                html_content += '<img src="%s"></img><HR></HR>'%fl
                shutil.copy(fname, os.path.join(os.path.dirname(data_file), fl))
        for fl in links:
            # The links contained into the Basket note node are appended at the end of the Keepnote note node
            html_content += '<a href="%s">%s</a><HR></HR>'%(fl,fl)                           
        return html_content


    def install_icon(self, icon):
        """Installs a new icon into the notebook icon store"""
        basename = os.path.basename(icon)
        newfilename = os.path.join(self.notebook.get_icon_dir(), basename)
        shutil.copy(icon, newfilename)
        return os.path.basename(newfilename)

    @classmethod
    def import_basket(cls, basket_xml_file, node, basket_directory, window):
        _p = cls()
        basketTree = ET.parse(basket_xml_file).getroot()
        return _p.parse(basketTree, node, basket_directory, window)    


HTML_HEAD="""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>Appunti</title>
</head><body> <br/>
"""
HTML_TAIL='</body></html>'

def write_node(node, html_content):
    """
        Write the note file associated to the node
    """
    fname = node.get_data_file()
    datastring = unescape(''.join(html_content))
    out = codecs.open(fname, "w","utf8")
    out.write(HTML_HEAD + datastring + HTML_TAIL)
    out.close() 


def get_xml_attr(attrs, name):
    """
        Returns the XML attribute "name", searching it into the attrs list "attrs"
    """
    # print "get_xml_attr: %s"%attrs
    for a in attrs:
        if a[0].upper() == name.upper():
            return a[1]
    return None

def read_html_file(fl):
    """
        Read each node*.html basket note fl filename,
        - try first opening it as utf8 and in case of failure, try again with latin1 encoding
        - gets only the HTML body text content, removing <html> <head> <body> <meta> and <style> tags
    """
    htmlcontent = ""
    # print "Opening file %s - "%fl,
    htmlcontent = text_file_read(fl)
    htmlcontent = HTMLFilter.filter_style(htmlcontent) # Remove <html> <head> <body> <meta> and <style> tags
    return htmlcontent



class BasketNodeDescParser(sgmllib.SGMLParser):
    """ A Basket notepad node description file parser:  .basket
        return:
        - a list of .html and .jpg/png/.gif ordered filenames which compose the node
        - a list of http:// file:// links
        Example of call: 
            (files, links) = BasketNodeDescParser.get_nodes_order(basket_node_directory)
    """
    def __init__(self, verbose=1):
        sgmllib.SGMLParser.__init__(self, verbose)
        
    def reset(self):
        # extend (called by SGMLParser.__init__)
        self.pieces = []
        sgmllib.SGMLParser.reset(self)
        self.file_list = []
        self.link_list = []
        
    def parse(self, basket_node_directory):
        
        data = codecs.open(os.path.join(basket_node_directory, ".basket"), "UTF8").read()
        
        self.feed(data)
        self.close()
        return (self.file_list, self.link_list)
    
    def handle_data(self, text):  
        if text != "\n":
            self.pieces.append(text)

    def start_content(self, attrs):
        """
            <content> tag found
        """
        # pieces variable collect read text
        self.pieces = []
        if get_xml_attr(attrs, "title") == None:
            self.is_link = False
        else:
            self.is_link = True
        
    def end_content(self):
        """
            </content> tag found, the pieces variable contains the <content> tag content, 
            a new html or gif/jpg/png file name has been found
        """
        flname = unescape(''.join(self.pieces))
        if not self.is_link:
            self.file_list.append(flname)
        else:
            self.link_list.append(flname)

    @classmethod
    def get_nodes_order(cls, basket_node_directory):
        _p = cls()
        return _p.parse(basket_node_directory)    

class HTMLFilter(HTMLParser.HTMLParser):
    '''A simple HTML transformer-class based upon HTMLParser. 
       All <html> <head> <body> <meta> and <style> tags are removed'''

    current_tag = ""
    tags_to_skip = ['style', 'html', 'head', 'meta', 'body']

    def __init__(self, *args, **kwargs):
        HTMLParser.HTMLParser.__init__(self)
        self.stack = []
        self._do_bold = False
        self._do_underline = False

    def handle_starttag(self, tag, attrs):
        self._do_bold = False
        self._do_underline = False
        self.current_tag = tag
        attrs = dict(attrs)
        if not tag.lower() in self.tags_to_skip:
            new_tag = self.__html_start_tag(tag, attrs)
            self.stack.append(new_tag)

    def handle_endtag(self, tag):
        if not tag.lower() in self.tags_to_skip:
            et = ''
            if tag == "span":
                level = len(self.stack)-1
                while level >= 0  and "<span" not in self.stack[level]:
                    level -= 1
                while level > 0 and "</span>" not in self.stack[level] and "</b>" not in self.stack[level] and "</u>" not in self.stack[level]:
                    try:
                        if  "<b>" in  self.stack[level]:
                            et += "</b>"
                    except IndexError:
                        pass
                    try:
                        if  "<u>" in  self.stack[level]:
                            et += "</u>"
                    except IndexError:
                        pass
                    level -= 1
            self.stack.append(self.__html_end_tag(tag))
            if et:
                self.stack.append(et)

    def handle_startendtag(self, tag, attrs):
        if not tag.lower() in self.tags_to_skip:
            attrs = dict(attrs)
            self.stack.append(self.__html_startend_tag(tag, attrs))

    def handle_data(self, data):
        if self.current_tag.lower() != 'style':
            self.stack.append(data)
    
    def __html_start_tag(self, tag, attrs):
        html_attrs = self.__html_attrs(attrs)
        st = ''
        if tag == "span":
            st = self.get_start_wrap()
        return '%s<%s%s>' % (st, tag, html_attrs)

    def __html_startend_tag(self, tag, attrs):
        return '<%s%s/>' % (tag, self.__html_attrs(attrs))

    def __html_end_tag(self, tag):
        return '</%s>' % (tag)

    def __html_attrs(self, attrs):
        _attrs = ''
        _style = ''
        _startwrap=''
        _endwrap=''
        if attrs:
            _attrs = ' %s' % ( ' '.join( [ ('%s="%s"' % (k,v)) for k,v in attrs.iteritems() if k != "style"] ) )
            if attrs.has_key("style"):
                _style =  attrs["style"]

                _not_style={} 
                for x in _style.split(";"):
                    if x and x not in ("font-size", "font-family", "text-align", "justify", "color", "background-color"):
                        _not_style[x.split(":")[0].strip()] = x.split(":")[1].strip()
                if _not_style and _not_style.has_key("text-decoration") and _not_style["text-decoration"]=="underline":
                    self._do_underline = True
                
                if _not_style and _not_style.has_key("font-weight"):
                    self._do_bold = True
                
                _style_list = _style.split(";")
                _style_list = filter(lambda x: x.split(":")[0].strip() in ("font-size", "font-family", "text-align", "justify", "color", "background-color"), _style.split(";"))
                i = 0                
                for _style in _style_list:
                    if "font-family" in _style:
                        _style_list[i] = "font-family: Monospace"
                        break
                    i += 1
                _style= ";".join(_style_list)
                if _style:
                    _attrs += ' style="%s"'%_style
              
        return _attrs
    
    def get_start_wrap(self):
        st = ''
        if self._do_bold:
            st += "<b>"
        if self._do_underline:
            st += "<u>"
        return st


    def filter(self, markup):
        self.feed(markup)
        self.close()
        return ''.join(self.stack)

    @classmethod
    def filter_style(cls, markup):
        _p = cls()
        return _p.filter(markup)
        


# adapted from io.py
# in the docutils extension module
# see http://docutils.sourceforge.net

def guess_encoding(data):
    """
    Given a byte string, attempt to decode it.
    Tries the standard 'UTF8' and 'latin-1' encodings,
    Plus several gathered from locale information.

    The calling program *must* first call 
        locale.setlocale(locale.LC_ALL, '')

    If successful it returns 
        (decoded_unicode, successful_encoding)
    If unsuccessful it raises a ``UnicodeError``
    """
    successful_encoding = None
    # we make 'utf-8' the first encoding
    encodings = ['utf-8']
    #
    # next we add anything we can learn from the locale
    try:
        encodings.append(locale.nl_langinfo(locale.CODESET))
    except AttributeError:
        pass
    try:
        encodings.append(locale.getlocale()[1])
    except (AttributeError, IndexError):
        pass
    try:
        encodings.append(locale.getdefaultlocale()[1])
    except (AttributeError, IndexError):
        pass
    #
    # we try 'latin-1' last
    encodings.append('latin-1')
    for enc in encodings:
        # some of the locale calls 
        # may have returned None
        if not enc:
            continue
        try:
            decoded = unicode(data, enc)
            successful_encoding = enc

        except (UnicodeError, LookupError):
            pass
        else:
            break
    if not successful_encoding:
         raise UnicodeError(
        'Unable to decode input data.  Tried the following encodings: %s.'
        % ', '.join([repr(enc) for enc in encodings if enc]))
    else:
         return (decoded, successful_encoding)


def text_file_read(filename):
    """
        Read the whole file, guessing its encoding
        return the whole file content as a unicode string
    """
    bomdict = { codecs.BOM_UTF8 : 'UTF8', 
                codecs.BOM_UTF16_BE : 'UTF-16BE', 
                codecs.BOM_UTF16_LE : 'UTF-16LE' }

    locale.setlocale(locale.LC_ALL, '')     # set the locale
    the_text = open(filename, 'rb').read()
    
    # check if there is Unicode signature
    for bom, encoding in bomdict.items():   
        if the_text.startswith(bom):
            the_text = the_text[len(bom):]
            break
        else:
            bom  = None
            encoding = None

    if encoding is None:    # there was no BOM
        try:
            unicode_text, encoding = guess_encoding(the_text)
        except UnicodeError:
            print "Sorry - we can't work out the encoding."
            raise
    else:                   
        # we found a BOM so we know the encoding
        unicode_text = the_text.decode(encoding)
    # print " file_read - selected encoding: %s"%encoding
    return unicode_text
        

