import os, shutil
import xml.dom.minidom as xmldom
import xml.dom

BLANK_NOTE = "<html><body></body></html>"

ELEMENT_NODE = 1
NODE_META_FILE = "node.xml"
PAGE_META_FILE = "page.xml"
PAGE_DATA_FILE = "page.html"
PREF_FILE = "notebook.nbk"


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

def get_pref_file(nodepath):
    return os.path.join(nodepath, PREF_FILE)


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
        self._title = title
        self._parent = parent
        self._set_basename(path)
        self._valid = True
        self._order = None
        self._children = None
        

    def create(self):
        """Initializes the node on disk"""
        path = self.get_path()
        os.mkdir(path)
        self.write_meta_data()


    def get_path(self):
        """Returns the directory path of the node"""
        if self._parent == None:
            return self.basename
        else:
            return os.path.join(self._parent.get_path(), self.basename)
    
    
    def _set_basename(self, path):
        """Sets the basename directory of the node"""
        if self._parent == None:
            self.basename = path
        else:
            self.basename = os.path.basename(path)
    
    
    def get_title(self):
        """Returns the display title of a node"""
        if self._title == None:
            self.read_meta_data()
        return self._title
    
    
    def get_parent(self):
        """Returns the parent of the node"""
        return self._parent
    
    
    def is_valid(self):
        """Returns True if node is valid (not deleted)"""
        return self._valid
        
    
    def delete(self):
        """Deletes this node from the notebook"""
        self._parent.remove_child(self)
        path = self.get_path()
        shutil.rmtree(path)
        self._valid = False
    
    
    def rename(self, title):
        """Renames the title of the node"""
        if title == self._title:
            return
        path = self.get_path()
        parent_path = os.path.dirname(path)
        path2 = get_valid_unique_filename(parent_path, title)

        try:
            os.rename(path, path2)
            self._title = title
            self._set_basename(path2)
            self.write_meta_data()
        except Exception, e:
            print e
            print "cannot rename '%s' to '%s'" % (path, path2)
    
    
    def load(self):
        self.read_meta_data()
    
    
    def save(self):
        """Recursively save any loaded nodes"""
        
        self.write_meta_data()
        self._save_children()
        
    
    def _save_children(self):
        """Recursively save any loaded child nodes"""
        if self._children is not None:
            for child in self._children:
                child.save()
        
    
    def get_meta_file(self):
        """Returns  the meta file filename for the node"""
        raise Exception("Unimplemented")
    
    def read_meta_data(self):
        """Reads the meta file for the node"""    
        raise Exception("Unimplemented")

    def write_meta_data(self):
        """Writes the meta file for the node"""
        raise Exception("Unimplemented")
    



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
                self._title = child.firstChild.nodeValue  

    def write_meta_data(self):
        
        out = open(self.get_meta_file(), "w")
        out.write("<page>\n")
        out.write("    <title>%s</title>\n" % self._title)
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
        page = NoteBookPage(newpath, title=title, parent=self)
        page.create()
        if self._children is None:
            self._get_children()
        self._children.append(page)
        return page
    
    
    def new_dir(self, title):
        path = self.get_path()
        newpath = get_valid_unique_filename(path, title)
        os.mkdir(newpath)
        node = NoteBookDir(newpath, title=title, parent=self)
        node.write_meta_data()
        if self._children is None:
            self._get_children()
        self._children.append(node)        
        return node
    
    
    def _get_children(self):
        self._children = []
        
        subdirs = os.listdir(self.get_path())
        subdirs.sort()
        
        for filename in subdirs:
            path2 = os.path.join(self.get_path(), filename)
            nodefile = get_dir_meta_file(path2)
            pagefile = get_page_meta_file(path2)
            if os.path.isdir(path2) and os.path.exists(nodefile):
                node = NoteBookDir(path2, parent=self)
                node.read_meta_data()
                self._children.append(node)
                
            elif os.path.isdir(path2) and os.path.exists(pagefile):
                page = NoteBookPage(path2, parent=self)
                page.read_meta_data()
                self._children.append(page)

    def get_children(self):
        if self._children is None:
            self._get_children()
        
        for child in self._children:
            if isinstance(child, NoteBookDir):
                yield child
    
    
    def get_pages(self):
        if self._children is None:
            self._get_children()
        
        for child in self._children:
            if isinstance(child, NoteBookPage):
                yield child

    def remove_child(self, child):
        if self._children is None:
            self._get_children()
        self._children.remove(child)
                
    
    def read_meta_data(self):
        
        dom = xmldom.parse(self.get_meta_file())
        
        root = dom.firstChild
        assert root != None
        
        for child in get_dom_children(root):
            if child.nodeType == ELEMENT_NODE and child.tagName == "title":
                self._title = child.firstChild.nodeValue
    
    def write_meta_data(self):
        
        out = open(self.get_meta_file(), "w")
        out.write("<node>\n")
        out.write("    <title>%s</title>\n" % self._title)
        out.write("</node>\n")
        out.close()


class NoteBookPreferences (object):
    def __init__(self):
        self.window_size = [800, 600]
        self.vsash_pos = 200
        self.hsash_pos = 200



class NoteBook (NoteBookDir):
    def __init__(self, rootdir):
        """rootdir -- Root directory of notebook"""
        NoteBookDir.__init__(self, rootdir)
        self.pref = NoteBookPreferences()

        
    def create(self):
        os.mkdir(self.get_path())
        self.write_meta_data()

    
    def get_root_node(self):
        """Returns the root node of the notebook"""
        return self
    
    
    def load(self):
        self.read_meta_data()
        self.read_preferences()
    
    
    def save(self):
        """Recursively save any loaded nodes"""
        
        self.write_meta_data()
        self.write_preferences()
        self._save_children()
    
    
    def get_pref_file(self):
        return get_pref_file(self.get_path())
    
    
    def write_preferences(self):
        out = open(self.get_pref_file(), "w")
        out.write("<notebook>\n")
        out.write("    <window_width>%d</window_width>\n" % 
            self.pref.window_size[0])
        out.write("    <window_height>%d</window_height>\n" % 
            self.pref.window_size[1])
        out.write("    <vsash_pos>%d</vsash_pos>\n" % self.pref.vsash_pos)
        out.write("    <hsash_pos>%d</hsash_pos>\n" % self.pref.hsash_pos)
        out.write("</notebook>\n")
        out.close()
    
    
    def read_preferences(self):
        
        dom = xmldom.parse(self.get_pref_file())
        
        root = dom.firstChild
        assert root != None
        
        for child in get_dom_children(root):
            if child.nodeType == ELEMENT_NODE:
                if child.tagName == "window_width":
                    self.pref.window_size[0] = int(child.firstChild.nodeValue)
                if child.tagName == "window_height":
                    self.pref.window_size[1] = int(child.firstChild.nodeValue)
                if child.tagName == "vsash_pos":
                    self.pref.vsash_pos = int(child.firstChild.nodeValue)
                if child.tagName == "hsash_pos":
                    self.pref.hsash_pos = int(child.firstChild.nodeValue)
                
