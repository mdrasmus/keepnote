import os
import xml.dom.minidom as xmldom
import xml.dom

BLANK_NOTE = "<html><body></body></html>"

ELEMENT_NODE = 1
NODE_META_FILE = "node.xml"
PAGE_META_FILE = "page.xml"
PAGE_DATA_FILE = "page.html"


#=============================================================================
# NoteBook data structures

def get_node_meta_file(nodepath):
    return os.path.join(nodepath, NODE_META_FILE)

def get_page_meta_file(pagepath):
    return os.path.join(pagepath, PAGE_META_FILE)

def get_page_data_file(pagepath):
    return os.path.join(pagepath, PAGE_DATA_FILE)


def get_dom_children(node):
    child = node.firstChild
    while child:
        yield child
        child = child.nextSibling


class NoteBook (object):
    def __init__(self, rootdir):
        """rootdir -- Root directory of notebook"""
            
        self.root = NoteBookNode(rootdir)
    
    
    def get_root_node(self):
        """Returns the root node of the notebook"""
        return self.root


    def new_page(self, parent_node, title):
        parent_node.new_page(title)


class NoteBookPage (object):
    def __init__(self, path, title=None, parent=None):
        self.title = title
        self.path = path
        self.parent = parent
        
        if os.path.exists(self.get_meta_file()):
            self.read_metadata()
        else:
            self.write_metadata()
        
        datafile = self.get_data_file()
        if not os.path.exists(datafile):
            out = open(datafile, "w")
            out.write("<html><body></body></html>")
            out.close()
    
    
    def get_path(self):
        return self.path
    
    
    def get_title(self):
        if self.title == None:
            self.read_metadata()
        return self.title
    
    def get_parent(self):
        return self.parent
    
    
    def get_data_file(self):
        return get_page_data_file(self.path)
    
    
    def get_meta_file(self):
        return get_page_meta_file(self.path)
    
    
    def read_metadata(self):
        dom = xmldom.parse(self.get_meta_file())
        
        root = dom.firstChild
        assert root != None
        
        for child in get_dom_children(root):
            if child.nodeType == ELEMENT_NODE and child.tagName == "title":
                self.title = child.firstChild.nodeValue  

    def write_metadata(self):
        
        out = open(self.get_meta_file(), "w")
        out.write("<page>\n")
        out.write("    <title>%s</title>\n" % self.title)
        out.write("</page>\n")
        out.close()


class NoteBookNode (object):
    def __init__(self, path, title=None, parent=None):
        self.path = path
        self.title = title
        self.parent = parent
        
        if os.path.exists(self.get_meta_file()):
            self.read_metadata()
        else:
            self.write_metadata()

    
    def get_path(self):
        return self.path
    
    def get_title(self):
        if self.title == None:
            self.read_metadata()
        return self.title
    
    def get_parent(self):
        return self.parent
        
    
    def get_meta_file(self):    
        return get_node_meta_file(self.path)
    
    
    def new_page(self, title):
        newpath = os.path.join(self.path, title)
        os.mkdir(newpath)
        return NoteBookPage(newpath, title=title)
    
    
    def new_node(self, title):
        newpath = os.path.join(self.path, title)
        os.mkdir(newpath)
        node = NoteBookNode(newpath, title=title)
        return node
        
        
    
    def rename(self, title):
        path2 = os.path.join(os.path.dirname(self.path), title)
        
        try:
            os.rename(self.path, path2)
            self.title = title
            self.path = path2
        except Exception, e:
            print e
            print "cannot rename page '%s' to '%s'" % (self.path, path2)
    
     
    def get_children(self):
        subdirs = os.listdir(self.path)
        subdirs.sort()
        
        for filename in subdirs:
            path2 = os.path.join(self.path, filename)
            nodefile = get_node_meta_file(path2)
            if os.path.isdir(path2) and os.path.exists(nodefile):
                yield NoteBookNode(path2, parent=self)
    
    
    def get_pages(self):
        files = os.listdir(self.path)
        files.sort()
        
        for filename in files:
            path2 = os.path.join(self.path, filename)
            pagefile = get_page_meta_file(path2)
            if os.path.isdir(path2) and os.path.exists(pagefile):
                yield NoteBookPage(path2, parent=self)
                
    
    def read_metadata(self):
        
        dom = xmldom.parse(self.get_meta_file())
        
        root = dom.firstChild
        assert root != None
        
        for child in get_dom_children(root):
            if child.nodeType == ELEMENT_NODE and child.tagName == "title":
                self.title = child.firstChild.nodeValue
    
    def write_metadata(self):
        
        out = open(self.get_meta_file(), "w")
        out.write("<node>\n")
        out.write("    <title>%s</title>\n" % self.title)
        out.write("</node>\n")
        out.close()
