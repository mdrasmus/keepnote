"""
    TakeNote
    Copyright Matt Rasmussen 2008

    Module for TakeNote
    
    Basic backend data structures for TakeNote and NoteBooks
"""

# TODO: add NoteBookException

import xmlobject as xmlo

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
NOTEBOOK_META_DIR = "__NOTEBOOK__"
USER_PREF_DIR = ".takenote"
USER_PREF_FILE = "takenote.xml"
DEFAULT_PAGE_NAME = "New Page"
DEFAULT_DIR_NAME = "New Folder"


DEFAULT_WINDOW_SIZE = (800, 600)
DEFAULT_WINDOW_POS = (-1, -1)
DEFAULT_VSASH_POS = 200
DEFAULT_HSASH_POS = 200

# determine UNIX Epoc (which should be 0, unless the current platform has a 
# different standard)
EPOC = time.mktime((1970, 1, 1, 0, 0, 0, 3, 1, 0)) - time.timezone

FORMAT = "%a %b %d %I:%M:%S %p %Y"

"""

0  	tm_year  	(for example, 1993)
1 	tm_mon 	range [1,12]
2 	tm_mday 	range [1,31]
3 	tm_hour 	range [0,23]
4 	tm_min 	range [0,59]
5 	tm_sec 	range [0,61]; see (1) in strftime() description
6 	tm_wday 	range [0,6], Monday is 0
7 	tm_yday 	range [1,366]
8 	tm_isdst 	0, 1 or -1; see below

"""

TM_YEAR, \
TM_MON, \
TM_MDAY, \
TM_HOUR, \
TM_MIN, \
TM_SEC, \
TM_WDAY, \
TM_YDAY, \
TM_ISDST = range(9)


BASEDIR = ""
def get_resource(*path_list):
    return os.path.join(BASEDIR, *path_list)



#=============================================================================
# filenaming scheme

def get_timestamp():
	return int(time.time() - EPOC)

def get_localtime():
    return time.localtime(time.time() + EPOC)

def get_str_timestamp(timestamp, current=None):
    if current is None:
        current = get_localtime()
    local = time.localtime(timestamp + EPOC)
    
    if local[TM_YEAR] == current[TM_YEAR]:
        if local[TM_MON] == current[TM_MON]:
            if local[TM_MDAY] == current[TM_MDAY]:
                return time.strftime("%I:%M %p", local)
            else:
                return time.strftime("%a, %d %I:%M %p", local)
        else:
	        return time.strftime("%a, %b %d %I:%M %p", local)        
    else:
	    return time.strftime("%a, %b %d %I:%M %p %Y", local)


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

def get_pref_dir(nodepath):
    return os.path.join(nodepath, NOTEBOOK_META_DIR)

def get_user_pref_dir(home=None):
    if home is None:
        home = os.getenv("HOME")
    return os.path.join(home, USER_PREF_DIR)

def get_user_pref_file(home=None):
    return os.path.join(get_user_pref_dir(home), USER_PREF_FILE)


def init_user_pref(home=None):
    pref_dir = get_user_pref_dir(home)
    pref_file = get_user_pref_file(home)
    
    if not os.path.exists(pref_dir):
        os.mkdir(pref_dir)
    
    if not os.path.exists(pref_file):
        out = open(pref_file, "w")
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        out.write("<takenote>\n")
        out.write("</takenote>\n")
    


#=============================================================================
# filename creation functions

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


#=============================================================================
# misc functions

def get_dom_children(node):
    """Convenience function for iterating the children of a DOM object"""
    child = node.firstChild
    while child:
        yield child
        child = child.nextSibling


#=============================================================================
# NoteBook data structures

class TakeNotePreferences (object):
    """Preference data structure for the TakeNote application"""
    
    def __init__(self):
        self.external_apps = {}
        

    def read(self):
        if not os.path.exists(get_user_pref_file()):
            # write default
            self.write()
        
        g_takenote_pref_parser.read(self, get_user_pref_file())
    
    def write(self):
        if not os.path.exists(get_user_pref_dir()):
            os.mkdir(get_user_pref_dir())
        
        g_takenote_pref_parser.write(self, get_user_pref_file())
        

g_takenote_pref_parser = xmlo.XmlObject(
    xmlo.Tag("takenote", tags=[
        xmlo.Tag("external_apps", tags=[
            xmlo.Tag("file_explorer", 
                get=lambda s,x: s.external_apps.__setitem__(
                    "file_explorer", x),
                set=lambda s: s.external_apps.get("file_explorer", "")),
            xmlo.Tag("web_browser", 
                get=lambda s,x: s.external_apps.__setitem__(
                    "web_browser", x),
                set=lambda s: s.external_apps.get("web_browser", "")),
            xmlo.Tag("image_editor", 
                get=lambda s,x: s.external_apps.__setitem__(
                    "image_editor", x),
                set=lambda s: s.external_apps.get("image_editor", "")),
            xmlo.Tag("text_editor", 
                get=lambda s,x: s.external_apps.__setitem__(
                    "text_editor", x),
                set=lambda s: s.external_apps.get("text_editor", "")),
                
            ])
        ]))
        



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
    
    def get_created_time(self):
        return self._created_time

    def get_created_time_text(self):
        return get_str_timestamp(self._created_time)
    
    def get_modified_time(self):
        return self._modified_time

    def get_modified_time_text(self):
        return get_str_timestamp(self._modified_time)
    
    
    def set_created_time(self, timestamp=None):
        if timestamp is None:
            self._created_time = get_timestamp()
            self._set_dirty(True)
        
    def set_modified_time(self, timestamp=None):
        if timestamp is None:
            self._modified_time = get_timestamp()
            self._set_dirty(True)
    
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
        self._set_dirty(False)
        
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
    
    
    def new_page(self, title=DEFAULT_PAGE_NAME):
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
    
    
    def new_dir(self, title=DEFAULT_DIR_NAME):
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
            
    
    
    def get_meta_file(self):
        """Returns  the meta file filename for the node"""
        raise Exception("Unimplemented")
    
    def read_meta_data(self):
        """Reads the meta file for the node"""    
        raise Exception("Unimplemented")

    def write_meta_data(self):
        """Writes the meta file for the node"""
        raise Exception("Unimplemented")
    


g_node_meta_data_tags = [
    xmlo.Tag("title", 
        getobj=("_title", None),
        set=lambda s: s._title),
    xmlo.Tag("order",
        getobj=("_order", int),
        set=lambda s: str(s._order)),
    xmlo.Tag("created_time",
        getobj=("_created_time", int),
        set=lambda s: str(s._created_time)),
    xmlo.Tag("modified_time",
        getobj=("_modified_time", int),
        set=lambda s: str(s._modified_time))]



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
        self._created_time = None
        self._modified_time = None    
    
        g_page_meta_data_parser.read(self, self.get_meta_file())
        
        if self._created_time is None:
            self._created_time = get_timestamp()
            self._set_dirty(True)
        if self._modified_time is None:
            self._modified_time = get_timestamp()
            self._set_dirty(True)

                
    
    def write_meta_data(self):
        g_page_meta_data_parser.write(self, self.get_meta_file())


g_page_meta_data_parser = xmlo.XmlObject(
    xmlo.Tag("page", tags=
        g_node_meta_data_tags))
            



class NoteBookDir (NoteBookNode):
    def __init__(self, path, title=None, parent=None, notebook=None):
        NoteBookNode.__init__(self, path, title, parent, notebook)
        
        
    def get_meta_file(self):    
        return get_dir_meta_file(self.get_path())
    
    
    def read_meta_data(self):
        self._created_time = None
        self._modified_time = None
        
        g_dir_meta_data_parser.read(self, self.get_meta_file())
        
        if self._created_time is None:
            self._created_time = get_timestamp()
            self._set_dirty(True)
        if self._modified_time is None:
            self._modified_time = get_timestamp()
            self._set_dirty(True)        
                
    def write_meta_data(self):
        g_dir_meta_data_parser.write(self, self.get_meta_file())



g_dir_meta_data_parser = xmlo.XmlObject(
    xmlo.Tag("node", tags=
        g_node_meta_data_tags + [
        xmlo.Tag("expanded",
            getobj=("_expanded", lambda x: bool(int(x))),
            set=lambda s: str(int(s._expanded))) ]))
            

    

class NoteBookPreferences (xmlo.XmlObject):
    """Preference data structure for a NoteBook"""
    def __init__(self):
        
        self.window_size = DEFAULT_WINDOW_SIZE
        self.window_pos = DEFAULT_WINDOW_POS
        self.vsash_pos = DEFAULT_VSASH_POS
        self.hsash_pos = DEFAULT_HSASH_POS

g_notebook_pref_parser = xmlo.XmlObject(
    xmlo.Tag("notebook", tags=[
        xmlo.Tag("window_size", 
            getobj=("window_size", lambda x: tuple(map(int,x.split(",")))),
            set=lambda s: "%d,%d" % s.window_size),
        xmlo.Tag("window_pos",
            getobj=("window_pos", lambda x: tuple(map(int,x.split(",")))),
            set=lambda s: "%d,%d" % s.window_pos),
        xmlo.Tag("vsash_pos",
            getobj=("vhash_pos", int),
            set=lambda s: "%d" % s.vsash_pos),
        xmlo.Tag("hsash_pos",
            getobj=("hsash_pos", int),
            set=lambda s: "%d" % s.hsash_pos)]))
            

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
        
    
    def save_needed(self):
        return len(self._dirty) > 0
        
        
    def create(self):
        NoteBookDir.create(self)
        os.mkdir(self.get_pref_dir())

    
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
        
        self._set_dirty(False)
        
        for node in list(self._dirty):
            node.save()
        
        assert len(self._dirty) == 0
    
    
    def get_pref_file(self):
        return get_pref_file(self.get_path())
    
    def get_pref_dir(self):
        return get_pref_dir(self.get_path())
    
    
    def write_preferences(self):
    
        # ensure preference directory exists
        if not os.path.exists(self.get_pref_dir()):
            os.mkdir(self.get_pref_dir())
        
        g_notebook_pref_parser.write(self.pref, self.get_pref_file())
    
    def read_preferences(self):
        g_notebook_pref_parser.read(self.pref, self.get_pref_file())

                
