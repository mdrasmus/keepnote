import os, shutil
import xml.dom.minidom as xmldom
import xml.dom

BLANK_NOTE = "<html><body></body></html>"

ELEMENT_NODE = 1
NODE_META_FILE = "node.xml"
PAGE_META_FILE = "page.xml"
PAGE_DATA_FILE = "page.html"


# TODO: add NoteBookException

#=============================================================================
# NoteBook data structures

def get_dir_meta_file(nodepath):
    """Returns the metadata file for a dir"""
    return os.path.join(nodepath, NODE_META_FILE)

def get_page_meta_file(pagepath):
    """Retruns the metadata file for a page"""
    return os.path.join(pagepath, PAGE_META_FILE)

def get_page_data_file(pagepath):
    """Returns the HTML data file for a page"""
    return os.path.join(pagepath, PAGE_DATA_FILE)


def get_dom_children(node):
    """Convenience function for iterating the children of a DOM object"""
    child = node.firstChild
    while child:
        yield child
        child = child.nextSibling

def get_valid_filename(filename):
    filename = filename.replace("/", "-")
    filename = filename.replace("'", "")
    return filename
    

def get_unique_filename(path, filename, ext="", sep=" ", number=2):
    if path != "":
        assert os.path.exists(path)
    
    # try the given filename
    newname = os.path.join(path, filename + ext)
    if not os.path.exists(newname):
        return newname
    
    # try numbered suffixes
    i = number
    while True:
        newname = os.path.join(path, filename + sep + str(i) + ext)
        if not os.path.exists(newname):
            return newname
        i += 1


def get_valid_unique_filename(path, filename, ext="", sep=" ", number=2):
    return get_unique_filename(path, get_valid_filename(filename), 
                               ext, sep, number)
    

def get_unique_filename_list(filenames, filename, ext="", sep=" ", number=2):
    filenames = set(filenames)
    
    # try the given filename
    newname = filename + ext
    if newname not in filenames:
        return newname
    
    # try numbered suffixes
    i = number
    while True:
        newname = filename + sep + str(i) + ext
        if newname not in filenames:
            return newname
        i += 1


class NoteBookNode (object):
    def __init__(self, path, title=None, parent=None):
        self.title = title
        self.parent = parent
        self._set_basename(path)
        

    def create(self):
        path = self.get_path()
        os.mkdir(path)
        self.write_meta_data()


    def get_path(self):
        if self.parent == None:
            return self.basename
        else:
            return os.path.join(self.parent.get_path(), self.basename)
    
    def _set_basename(self, path):
        if self.parent == None:
            self.basename = path
        else:
            self.basename = os.path.basename(path)
    
    def get_title(self):
        if self.title == None:
            self.read_meta_data()
        return self.title

    def get_parent(self):
        return self.parent
    
    def delete(self):
        path = self.get_path()
        shutil.rmtree(path)
    
    def rename(self, title):
        path = self.get_path()
        parent_path = os.path.dirname(path)
        path2 = get_valid_unique_filename(parent_path, title)

        try:
            os.rename(path, path2)
            self.title = title
            self._set_basename(path2)
            self.write_meta_data()
        except Exception, e:
            print e
            print "cannot rename '%s' to '%s'" % (path, path2)
    
    
    def get_meta_file(self):
        raise Exception("Unimplemented")
    
    def read_meta_data(self):
        raise Exception("Unimplemented")

    def write_meta_data(self):
        raise Exception("Unimplemented")

    def __eq__(self, other):
        if isinstance(other, NoteBookNode):
            return self.get_path() == other.get_path()
        else:
            return False


class NoteBookPage (NoteBookNode):
    def __init__(self, path, title=None, parent=None):
        NoteBookNode.__init__(self, path, title, parent)
    
    
    def create(self):
        self.write_meta_data()
        self.write_empty_data_file()
    

    def get_data_file(self):
        return get_page_data_file(self.get_path())
    
    
    def get_meta_file(self):
        return get_page_meta_file(self.get_path())
        
    
    def write_empty_data_file(self):
        datafile = self.get_data_file()
        out = open(datafile, "w")
        out.write("<html><body></body></html>")
        out.close()
    
    
    def read_meta_data(self):
        dom = xmldom.parse(self.get_meta_file())
        
        root = dom.firstChild
        assert root != None
        
        for child in get_dom_children(root):
            if child.nodeType == ELEMENT_NODE and child.tagName == "title":
                self.title = child.firstChild.nodeValue  

    def write_meta_data(self):
        
        out = open(self.get_meta_file(), "w")
        out.write("<page>\n")
        out.write("    <title>%s</title>\n" % self.title)
        out.write("</page>\n")
        out.close()


class NoteBookDir (NoteBookNode):
    def __init__(self, path, title=None, parent=None):
        NoteBookNode.__init__(self, path, title, parent)
    
        
    def get_meta_file(self):    
        return get_dir_meta_file(self.get_path())
    
    
    def new_page(self, title):
        path = self.get_path()
        newpath = get_valid_unique_filename(path, title)
        os.mkdir(newpath)
        page = NoteBookPage(newpath, title=title)
        page.create()
        return page
    
    
    def new_dir(self, title):
        path = self.get_path()
        newpath = get_valid_unique_filename(path, title)
        os.mkdir(newpath)
        node = NoteBookDir(newpath, title=title, parent=self)
        node.write_meta_data()
        return node
    
     
    def get_children(self):
        subdirs = os.listdir(self.get_path())
        subdirs.sort()
        
        for filename in subdirs:
            path2 = os.path.join(self.get_path(), filename)
            nodefile = get_dir_meta_file(path2)
            if os.path.isdir(path2) and os.path.exists(nodefile):
                node = NoteBookDir(path2, parent=self)
                node.read_meta_data()
                yield node
    
    
    def get_pages(self):
        path = self.get_path()
        files = os.listdir(path)
        files.sort()
        
        for filename in files:
            path2 = os.path.join(path, filename)
            pagefile = get_page_meta_file(path2)
            if os.path.isdir(path2) and os.path.exists(pagefile):
                page = NoteBookPage(path2, parent=self)
                page.read_meta_data()
                yield page
                
    
    def read_meta_data(self):
        
        dom = xmldom.parse(self.get_meta_file())
        
        root = dom.firstChild
        assert root != None
        
        for child in get_dom_children(root):
            if child.nodeType == ELEMENT_NODE and child.tagName == "title":
                self.title = child.firstChild.nodeValue
    
    def write_meta_data(self):
        
        out = open(self.get_meta_file(), "w")
        out.write("<node>\n")
        out.write("    <title>%s</title>\n" % self.title)
        out.write("</node>\n")
        out.close()




class NoteBook (NoteBookDir):
    def __init__(self, rootdir):
        """rootdir -- Root directory of notebook"""
        NoteBookDir.__init__(self, rootdir)
        
    def create(self):
        os.mkdir(self.get_path())
        self.write_meta_data()
    
    def get_root_node(self):
        """Returns the root node of the notebook"""
        return self

