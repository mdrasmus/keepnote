"""
    TakeNote
    Copyright Matt Rasmussen 2008

    Module for TakeNote
    
    Basic backend data structures for TakeNote and NoteBooks
"""

# TODO: add NoteBookException


# python imports
import os, sys, shutil, time
import xml.dom.minidom as xmldom
import xml.dom



# constants
BLANK_NOTE = "<html><body></body></html>"

ELEMENT_NODE = 1
NODE_META_FILE = "node.xml"
PAGE_META_FILE = "page.xml"
PAGE_DATA_FILE = "page.html"
PREF_FILE = "notebook.nbk"


DEFAULT_WINDOW_SIZE = (800, 600)
DEFAULT_WINDOW_POS = (-1, -1)
DEFAULT_VSASH_POS = 200
DEFAULT_HSASH_POS = 200

# determine UNIX Epoc (which should be 0, unless the current platform has a 
# different standard)
EPOC = time.mktime((1970, 1, 1, 0, 0, 0, 3, 1, 0)) - time.timezone




#=============================================================================
# NoteBook data structures

def get_timestamp():
	return int(time.time() - EPOC)

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
    filename = filename.replace("\\", "-")
    filename = filename.replace("'", "")
    return filename
    

def get_unique_filename(path, filename, ext="", sep=" ", number=2):
    if path != "":
        assert os.path.exists(path), path
    
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
    def __init__(self, path, title=None, parent=None, notebook=None):
        self._notebook = notebook
        self._title = title
        self._parent = parent
        self._basename = None
        self._created_time = None
        self._modified_time = None
        self._valid = True
        self._order = sys.maxint
        self._children = None
        self._expanded = False
        
        self._set_basename(path)
        

    def create(self):
        """Initializes the node on disk"""
        path = self.get_path()
        os.mkdir(path)
        self._created_time = get_timestamp()
        self._modified_time = get_timestamp()
        self.write_meta_data()
        self._set_dirty(False)


    def get_path(self):
        """Returns the directory path of the node"""
        
        path_list = []
        ptr = self
        while ptr != None:
            path_list.append(ptr._basename)
            ptr = ptr._parent
        path_list.reverse()
        
        return os.path.join(* path_list)
            
    
    def _set_basename(self, path):
        """Sets the basename directory of the node"""
        if self._parent == None:
            self._basename = path
        elif path is None:
            self._basename = None
        else:
            self._basename = os.path.basename(path)
    
    
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
    
    
    def is_page(self):
        return False
    
    def set_expand(self, expanded):
        self._expanded = expanded
        self._set_dirty(True)
    
    def is_expanded(self):
        return self._expanded


    def _set_dirty(self, dirty):
        self._notebook._set_dirty_node(self, dirty)
        
    def _is_dirty(self):
        return self._notebook._is_dirty_node(self)

    
    def move(self, parent, index=None):
        assert self != parent
        path = self.get_path()
        old_parent = self._parent
        self._parent.remove_child(self)
        self._parent = parent
        self._parent.add_child(self, index)
        self._set_dirty(True)
        
        # perform on-disk move is new parent
        if old_parent != self._parent:
            path2 = self.get_path()
            parent_path = os.path.dirname(path2)
            path2 = get_valid_unique_filename(parent_path, self._title)
            os.rename(path, path2)
            self.save(True)
        
    
    def delete(self):
        """Deletes this node from the notebook"""
        self._parent.remove_child(self)
        path = self.get_path()
        shutil.rmtree(path)
        self._valid = False
        
        # make sure to recursively invalidate
        self._invalidate_children()
        
    
    def _invalidate_children(self):
        
        if self._children is not None:
            for child in self._children:
                child._valid = False
                child._invalidate_children()
    
    
    def rename(self, title):
        """Renames the title of the node"""
        
        # do noting if title is the same
        if title == self._title:
            return
        
        if self._parent is None:
            # don't rename the directory of the notebook itself
            # just change the title
            self._title = title
            self._set_dirty(True)
            return
        
        # try to pick a path that closely resembles the title
        path = self.get_path()
        parent_path = os.path.dirname(path)
        path2 = get_valid_unique_filename(parent_path, title)

        try:
            os.rename(path, path2)
            self._title = title
            self._set_basename(path2)
            self.save(True)
        except Exception, e:
            print e
            print "cannot rename '%s' to '%s'" % (path, path2)
    
    
    def new_page(self, title):
        path = self.get_path()
        newpath = get_valid_unique_filename(path, title)
        page = NoteBookPage(newpath, title=title, parent=self, notebook=self._notebook)
        page.create()
        if self._children is None:
            self._get_children()
        page._order = len(self._children)
        self._children.append(page)
        page.save(True)
        return page
    
    
    def new_dir(self, title):
        path = self.get_path()
        newpath = get_valid_unique_filename(path, title)
        node = NoteBookDir(newpath, title=title, parent=self, notebook=self._notebook)
        node.create()
        if self._children is None:
            self._get_children()
        node._order = len(self._children)
        self._children.append(node)
        node.save(True)
        return node
    
    
    def _get_children(self):
        self._children = []
        path = self.get_path()
        
        files = os.listdir(path)
        
        for filename in files:
            path2 = os.path.join(path, filename)
            nodefile = get_dir_meta_file(path2)
            pagefile = get_page_meta_file(path2)
            
            if os.path.exists(nodefile):
                # create dir node
                node = NoteBookDir(path2, parent=self, notebook=self._notebook)
                node.read_meta_data()
                self._children.append(node)
                
            elif os.path.exists(pagefile):
                # create page node
                page = NoteBookPage(path2, parent=self, notebook=self._notebook)
                page.read_meta_data()
                self._children.append(page)
        
        # assign orders
        self._children.sort(key=lambda x: x._order)
        self._set_child_order()
    
    def _set_child_order(self):
        for i, child in enumerate(self._children):
            if child._order != i:
                child._order = i
                child._set_dirty(True)
            

    def add_child(self, child, index):
        child._notebook = self._notebook
        
        if self._children is None:
            self._get_children()
        
        if index == None:
            child._order = self._children[-1]._order + 1
            self._children.append(child)
        else:
            self._children.insert(index, child)
            self._set_child_order()
        child._set_dirty(True)

        

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
           
    
    def load(self):
        self.read_meta_data()
    
    
    def save(self, force=False):
        """Recursively save any loaded nodes"""
        
        if (force or self._is_dirty()) and self._valid:
            self.write_meta_data()
            self._set_dirty(False)
            
        #self._save_children()
            
        
    '''
    def _save_children(self):
        """Recursively save any loaded child nodes"""
        if self._children is not None:
            for child in self._children:
                child.save()
    ''' 
    
    
    def get_meta_file(self):
        """Returns  the meta file filename for the node"""
        raise Exception("Unimplemented")
    
    def read_meta_data(self):
        """Reads the meta file for the node"""    
        raise Exception("Unimplemented")

    def write_meta_data(self):
        """Writes the meta file for the node"""
        raise Exception("Unimplemented")
    
    def read_basic_meta_data(self, child):
        if child.tagName == "title":
            self._title = child.firstChild.nodeValue
        if child.tagName == "order":
            self._order = int(child.firstChild.nodeValue)
        if child.tagName == "created_time":
            self._created_time = int(child.firstChild.nodeValue)
        if child.tagName == "modified_time":
            self._modified_time = int(child.firstChild.nodeValue)
        
    
    def write_basic_meta_data(self, out):
        out.write("    <title>%s</title>\n" % self._title)
        out.write("    <order>%d</order>\n" % self._order)
        out.write("    <created_time>%d</created_time>\n" % self._created_time)
        out.write("    <modified_time>%d</modified_time>\n" % self._modified_time)



class NoteBookPage (NoteBookNode):
    def __init__(self, path, title=None, parent=None, notebook=None):
        NoteBookNode.__init__(self, path, title, parent, notebook)
    
    
    def create(self):
        NoteBookNode.create(self)
        self.write_empty_data_file()
    
    def is_page(self):
        return True
    
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
        
        self._created_time = None
        self._modified_time = None
        
        for child in get_dom_children(root):
            if child.nodeType == ELEMENT_NODE:
                self.read_basic_meta_data(child)
        
        if self._created_time is None:
            self._created_time = get_timestamp()
            self._set_dirty(True)
        if self._modified_time is None:
            self._modified_time = get_timestamp()
            self._set_dirty(True)

                
    
    def write_meta_data(self):
        
        out = open(self.get_meta_file(), "w")
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        out.write("<page>\n")
        self.write_basic_meta_data(out)
        out.write("</page>\n")
        out.close()



class NoteBookDir (NoteBookNode):
    def __init__(self, path, title=None, parent=None, notebook=None):
        NoteBookNode.__init__(self, path, title, parent, notebook)
        
        
    def get_meta_file(self):    
        return get_dir_meta_file(self.get_path())
    
    
    def read_meta_data(self):
        
        dom = xmldom.parse(self.get_meta_file())
        
        root = dom.firstChild
        assert root != None
        
        self._created_time = None
        self._modified_time = None
       
        for child in get_dom_children(root):
            if child.nodeType == ELEMENT_NODE:
                self.read_basic_meta_data(child)
                if child.tagName == "expanded":
                    self._expanded = bool(int(child.firstChild.nodeValue))
        
        if self._created_time is None:
            self._created_time = get_timestamp()
            self._set_dirty(True)
        if self._modified_time is None:
            self._modified_time = get_timestamp()
            self._set_dirty(True)
    
    
    def write_meta_data(self):
        out = open(self.get_meta_file(), "w")
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        out.write("<node>\n")
        self.write_basic_meta_data(out)
        out.write("    <expanded>%d</expanded>\n" % int(self._expanded))
        out.write("</node>\n")
        out.close()


class NoteBookPreferences (object):
    """Preference data structure for a NoteBook"""
    def __init__(self):
        self.window_size = DEFAULT_WINDOW_SIZE
        self.window_pos = DEFAULT_WINDOW_POS
        self.vsash_pos = DEFAULT_VSASH_POS
        self.hsash_pos = DEFAULT_HSASH_POS



class NoteBook (NoteBookDir):
    def __init__(self, rootdir=None):
        """rootdir -- Root directory of notebook"""
        NoteBookDir.__init__(self, rootdir)
        self.pref = NoteBookPreferences()
        if rootdir is not None:
            self._title = os.path.basename(rootdir)
        else:
            self._title = None
        self._dirty = set()
        self._notebook = self

    def _set_dirty_node(self, node, dirty):
        if dirty:
            self._dirty.add(node)
        else:
            if node in self._dirty:
                self._dirty.remove(node)
    
    
    def _is_dirty_node(self, node):
        return node in self._dirty
        
        
    #def create(self):
    #    os.mkdir(self.get_path())
    #    self.write_meta_data()

    
    def get_root_node(self):
        """Returns the root node of the notebook"""
        return self
    
    
    def load(self, filename=None):
        if filename is not None:
            if os.path.isdir(filename):
                self._set_basename(filename)
            elif os.path.isfile(filename):
                filename = os.path.dirname(filename)
                self._set_basename(filename)
            else:
                raise Exception("cannot load notebook '%s'" % filename)
        self.read_meta_data()
        self.read_preferences()
    
    
    def save(self, force=False):
        """Recursively save any loaded nodes"""
        
        self.write_meta_data()
        self.write_preferences()
        #self._save_children()
        
        self._set_dirty(False)
        
        for node in list(self._dirty):
            node.save()
        
        assert len(self._dirty) == 0
    
    
    def get_pref_file(self):
        return get_pref_file(self.get_path())
    
    
    def write_preferences(self):
        out = open(self.get_pref_file(), "w")
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        out.write("<notebook>\n")
        out.write("    <window_size>%d,%d</window_size>\n" % 
            tuple(self.pref.window_size))
        out.write("    <window_pos>%d,%d</window_pos>\n" % 
            tuple(self.pref.window_pos))
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
                if child.tagName == "window_size":
                    self.pref.window_size = map(int,child.firstChild.nodeValue.split(","))
                if child.tagName == "window_pos":
                    self.pref.window_pos = map(int,child.firstChild.nodeValue.split(","))
                if child.tagName == "vsash_pos":
                    self.pref.vsash_pos = int(child.firstChild.nodeValue)
                if child.tagName == "hsash_pos":
                    self.pref.hsash_pos = int(child.firstChild.nodeValue)
                
