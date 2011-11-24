"""

    KeepNote    
    Notebook data structure

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@alum.mit.edu>
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
import os, sys, shutil, time, re

# keepnote imports
import keepnote.compat.xmlobject_v1 as xmlo
from keepnote.listening import Listeners
from keepnote.timestamp import \
     DEFAULT_TIMESTAMP_FORMATS, \
     get_timestamp, \
     get_localtime, \
     get_str_timestamp
from keepnote import safefile


# constants
BLANK_NOTE = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"><body></body></html>"""

XML_HEADER = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"

NOTEBOOK_FORMAT_VERSION = 1
ELEMENT_NODE = 1
NODE_META_FILE = "node.xml"
PAGE_META_FILE = "page.xml"
PAGE_DATA_FILE = "page.html"
PREF_FILE = "notebook.nbk"
NOTEBOOK_META_DIR = "__NOTEBOOK__"
TRASH_DIR = "__TRASH__"
TRASH_NAME = "Trash"
DEFAULT_PAGE_NAME = "New Page"
DEFAULT_DIR_NAME = "New Folder"
DEFAULT_FONT_FAMILY = "Sans"
DEFAULT_FONT_SIZE = 10
DEFAULT_FONT = "%s %d" % (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)


# information sort constants
INFO_SORT_NONE, \
INFO_SORT_MANUAL, \
INFO_SORT_TITLE, \
INFO_SORT_CREATED_TIME, \
INFO_SORT_MODIFIED_TIME = range(5)


#=============================================================================
# filename creation functions

REGEX_SLASHES = re.compile(r"[/\\]")
REGEX_BAD_CHARS = re.compile(r"[\?'&<>|`:;]")

def get_valid_filename(filename, default="folder"):
    """Converts a filename into a valid one
    
    Strips bad characters from filename
    """
    
    filename = re.sub(REGEX_SLASHES, "-", filename)
    filename = re.sub(REGEX_BAD_CHARS, "", filename)
    filename = filename.replace("\t", " ")
    filename = filename.strip()
    
    # don't allow files to start with two underscores
    if filename.startswith("__"):
        filename = filename[2:]
    
    # don't allow pure whitespace filenames
    if filename == "":
        filename = default
    
    # use only lower case, some filesystems have trouble with mixed case
    filename = filename.lower()
    
    return filename
    

def get_unique_filename(path, filename, ext="", sep=" ", number=2):
    """Returns a unique version of a filename for a given directory"""

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
    """Returns a valid and unique version of a filename for a given path"""
    return get_unique_filename(path, get_valid_filename(filename), 
                               ext, sep, number)
    

def get_unique_filename_list(filenames, filename, ext="", sep=" ", number=2):
    """Returns a unique filename for a given list of existing files"""
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
# File naming scheme


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
    """Returns the filename of the notebook preference file"""
    return os.path.join(nodepath, PREF_FILE)

def get_pref_dir(nodepath):
    """Returns the directory of the notebook preference file"""
    return os.path.join(nodepath, NOTEBOOK_META_DIR)

def get_trash_dir(nodepath):
    """Returns the trash directory of the notebook"""
    return os.path.join(nodepath, TRASH_DIR)


#=============================================================================
# HTML functions

TAG_PATTERN = re.compile("<[^>]*>")
def strip_tags(line):
    return re.sub(TAG_PATTERN, "", line)

def read_data_as_plain_text(infile):
    """Read a Note data file as plain text"""

    for line in infile:
        # skip until body tag
        if "<body>" in line:
            pos = line.find("<body>")
            if pos != -1:
                yield strip_tags(line[pos+6:])
                break

    # yield until </body>
    for line in infile:
        pos = line.find("</body>")
        if pos != -1:
            yield strip_tags(line[:pos])
            break

        # strip tags
        yield strip_tags(line)


#=============================================================================
# notebook functions

def update_notebook(filename, desired_version):
    """Updates a notebook to the desired version (downgrading not implemented)"""

    # try to open notebook (may raise exceptions)
    notebook = Notebook()
    notebook.load(filename)

    if notebook.version >= desired_version:
        return


    # NOTE: for now, this code only works for version 1 to 2

    assert desired_version == 2

    if notebook.version == 1:
        from keepnote.backcompat import notebook_v1 as old_notebooklib

        # try to load old notebook (may raise exceptions)
        old_notebook = old_notebooklib.Notebook()
        old_notebook.load(filename)

        def walk(node):
            for child in node.get_children():
                # write to "node.xml" meta file
                child.write_meta_data2()

                # remove old "page.xml" meta file
                if isinstance(child, old_notebooklib.NoteBookPage):
                    try:
                        os.remove(child.get_meta_file())
                    except:
                        pass
            



#=============================================================================
# classes

class NoteBookError (StandardError):
    """Exception that occurs when manipulating NoteBook's"""
    
    def __init__(self, msg, error=None):
        StandardError.__init__(self)
        self.msg = msg
        self.error = error
    
    
    def __str__(self):
        if self.error:
            return str(self.error) + "\n" + self.msg
        else:
            return self.msg


class NoteBookVersionError (NoteBookError):
    """Exception for version errors while reading notebooks"""

    def __init__(self, notebook_version, readable_version,  error=None):
        NoteBookError.__init__(self,
            "Notebook version '%d' is higher than what is readable '%d'" %
                               (notebook_version,
                                readable_version),
                               error)
        self.notebook_version = notebook_version
        self.readable_version = readable_version

# TODO: finish

class NoteBookAttr (object):

    def __init__(self, name, datatype, key=None, write=None, read=None):
        if key == None:
            self.key = name
        else:
            self.key = key
        self.name = name
        self.datatype = datatype

        
        # writer function
        if write is None:
            if datatype == bool:
                self.write = lambda x: unicode(int(x))
            else:
                self.write = unicode
        else:
            self.write = write

        # reader function
        if read is None:
            if datatype == bool:
                self.read = lambda x: bool(int(x))
            else:
                self.read = datatype
        else:
            self.read = read
        

class NoteBookTable (object):
    def __init__(self, name):
        self.name = name
        self.cols = []

        # TODO: add col widths
        # NoteBooks have tables and attrs

g_default_attrs = [
    NoteBookAttr("Title", unicode, "title"),
    NoteBookAttr("Kind", unicode, "kind"),
    NoteBookAttr("Order", int, "order"),
    NoteBookAttr("Created", int, "created_time"),
    NoteBookAttr("Modified", int, "modified_time"),
    NoteBookAttr("Expaned", bool, "expanded"),
    NoteBookAttr("Expanded2", bool, "expanded2"),
    NoteBookAttr("Folder Sort", int, "info_sort"),
    NoteBookAttr("Folder Sort Direction", int, "info_sort_dir")
]


# TODO: parent might be an implict attr


# 1. attrs should be data that is optional (although keepnote has a few
# required entries).
# 2. attrs can appear in listview



class NoteBookNode (object):
    """A general base class for all nodes in a NoteBook"""

    def __init__(self, path, title="", parent=None, notebook=None, kind="dir"):
        self._notebook = notebook
        self._parent = parent
        self._basename = None
        self._children = None        
        self._valid = True
        self._version = NOTEBOOK_FORMAT_VERSION
        
        self._attr = {
            "title": title,
            "kind": kind,
            "order": sys.maxint,
            "created_time": None,
            "modified_time": None,
            "expanded": False,
            "expanded2": False,
            "info_sort": INFO_SORT_NONE,
            "info_sort_dir": 1}

        # TODO: add a mechanism to register implict attrs that in turn do lookup
        # "type", "title", "parent", "nchildren"
        
        self._set_basename(path)
        
        

    def create(self):
        """Initializes the node on disk (create required files/directories)"""
        path = self.get_path()
        
        try:
            os.mkdir(path)
        except OSError, e:
            raise NoteBookError("Cannot create node", e)
            
        self._attr["created_time"] = get_timestamp()
        self._attr["modified_time"] = get_timestamp()
        self.write_meta_data()
        self._set_dirty(False)

        if self._attr["kind"] == "page":
            self.write_empty_data_file()



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
        if self._attr["title"] == None:
            self.read_meta_data()
        return self._attr["title"]
    
    
    def get_parent(self):
        """Returns the parent of the node"""
        return self._parent

    def get_notebook(self):
        """Returns the notebook that owns this node"""
        return self._notebook

    def get_order(self):
        #assert self._parent is not None
        #assert self._parent.get_children().index(self) == self._order
        return self._attr["order"]
    
    def is_valid(self):
        """Returns True if node is valid (not deleted)"""
        return self._valid
    
    def is_page(self):
        """Returns True if node is a page"""
        return self._attr["kind"] == "page"
    
    def get_attr(self, name, default=None):
        return self._attr.get(name, default)

    def set_attr(self, name, value):
        self._attr[name] = value
        self._set_dirty(True)

    def set_attr_timestamp(self, name, timestamp=None):
        """Set a timestamp attribute"""
        if timestamp is None:
            timestamp = get_timestamp()
        self._attr[name] = timestamp
        self._set_dirty(True)
            

    def set_info_sort(self, info, sort_dir):
        """Sets the sorting information of the node"""
        self._attr["info_sort"] = info
        self._attr["info_sort_dir"] = sort_dir
        self._set_dirty(True)
    
    def get_info_sort(self):
        """Gets the sorting information of the node"""
        return (self._attr["info_sort"], self._attr["info_sort_dir"])

    def _set_dirty(self, dirty):
        """Sets the dirty bit to indicates whether node needs saving"""
        self._notebook._set_dirty_node(self, dirty)
        
    def _is_dirty(self):
        """Returns True if node needs saving"""
        return self._notebook._is_dirty_node(self)

    
    def move(self, parent, index=None):
        """Move this node to be the child of another node 'parent'"""
        
        assert self != parent
        path = self.get_path()
        old_parent = self._parent
        
        # perform on-disk move if new parent
        if old_parent != parent:
            path2 = os.path.join(parent.get_path(), self._basename)
            parent_path = os.path.dirname(path2)
            path2 = get_valid_unique_filename(parent_path, self._attr["title"])
            
            try:
                os.rename(path, path2)
            except OSError, e:
                raise NoteBookError("Do not have permission for move", e)
        
            self._set_basename(path2)

        # perform move in data structure
        self._parent._remove_child(self)
        if self._parent != parent:
            self._parent._set_child_order()
            self._parent = parent
            self._parent._add_child(self, index)
        else:
            if self._attr["order"] < index:
                index -= 1
            self._parent._add_child(self, index)
        self._set_dirty(True)
        self.save(True)

        # notify listeners
        if parent != old_parent:
            self.notify_changes([old_parent, parent], True)
        else:
            old_parent.notify_change(True)

        
    
    def delete(self):
        """Deletes this node from the notebook"""

        path = self.get_path()
        try:      
            shutil.rmtree(path)
        except OSError, e:
            raise NoteBookError("Do not have permission to delete", e)
        
        self._parent._remove_child(self)
        self._parent._set_child_order()
        self._valid = False
        self._set_dirty(False)
        
        # make sure to recursively invalidate
        self._invalidate_children()

        # parent node notifies listeners of change
        self._parent.notify_change(True)
    
    
    def trash(self):
        """Places node in the notebook's trash folder"""

        if self._notebook is None:
            raise NoteBookError("This node is not part of any notebook")
        
        if self.in_trash():
            # delete if in trash folder already
            self.delete()
            
        else:
            # move to trash            
            self.move(self._notebook._trash)
        
        
    
    def in_trash(self):
        """Determines if node is inside Trash folder"""
        
        ptr = self._parent
        while ptr is not None:
            if ptr == self._notebook._trash:
                return True
            ptr = ptr._parent
        return False
            
    
    def _invalidate_children(self):
        """Uncache children list"""
        
        if self._children is not None:
            for child in self._children:
                child._valid = False
                child._invalidate_children()
    
    
    def rename(self, title):
        """Renames the title of the node"""
        
        # do noting if title is the same
        if title == self._attr["title"]:
            return
        
        if self._parent is None:
            # don't rename the directory of the notebook itself
            # just change the title
            self._attr["title"] = title
            self._set_dirty(True)
            return
        
        # try to pick a path that closely resembles the title
        path = self.get_path()
        parent_path = os.path.dirname(path)
        path2 = get_valid_unique_filename(parent_path, title)

        try:
            os.rename(path, path2)
            self._attr["title"] = title
            self._set_basename(path2)
            self.save(True)
        except (OSError, NoteBookError), e:
            raise NoteBookError("Cannot rename '%s' to '%s'" % (path, path2), e)
        
        self.notify_change(False)


    # TODO: refactor this to a kind argument and make a factory function...
    
    def new_page(self, title=DEFAULT_PAGE_NAME):
        """Add a new page under node"""
        path = self.get_path()
        newpath = get_valid_unique_filename(path, title)
        page = NoteBookPage(newpath, title=title, parent=self,
                            notebook=self._notebook)
        page.create()
        self._add_child(page)
        page.save(True)
        self.notify_change(True)
        return page
    
    
    def new_dir(self, title=DEFAULT_DIR_NAME):
        """Add a new folder under node"""
        path = self.get_path()
        newpath = get_valid_unique_filename(path, title)
        node = NoteBookDir(newpath, title=title, parent=self,
                           notebook=self._notebook)
        node.create()
        self._add_child(node)
        node.save(True)
        self.notify_change(True)
        return node
    
    
    def _get_children(self):
        """Load children list from filesystem"""
        self._children = []
        path = self.get_path()
        
        try:
            files = os.listdir(path)
        except OSError, e:
            raise NoteBookError("Do not have permission to read folder contents", e)
        
        for filename in files:
            path2 = os.path.join(path, filename)
            nodefile = get_dir_meta_file(path2)
            pagefile = get_page_meta_file(path2)
            
            try:
                if filename == TRASH_DIR:
                    # create trash node
                    node = NoteBookTrash(TRASH_NAME, self._notebook)
                    
                elif os.path.exists(nodefile):
                    # create dir node
                    node = NoteBookDir(path2, parent=self,
                                       notebook=self._notebook)

                elif os.path.exists(pagefile):
                    # create page node
                    node = NoteBookPage(path2, parent=self,
                                        notebook=self._notebook)
                else:
                    # ignore file/directory
                    continue

                node.read_meta_data()
                self._children.append(node)

                
            except NoteBookError, e:
                continue                
                # TODO: raise warning, not all children read
            
                
        
        # assign orders
        self._children.sort(key=lambda x: x._attr["order"])
        self._set_child_order()
    
    def _set_child_order(self):
        """Ensures that child know their order in the children list"""
        for i, child in enumerate(self._children):
            if child._attr["order"] != i:
                child._attr["order"] = i
                child._set_dirty(True)
            

    def _add_child(self, child, index=None):
        """Add a node as a child"""
        
        # propogate notebook
        child._notebook = self._notebook
        
        if self._children is None:
            self._get_children()
        
        if index is not None:
            # insert child at index
            self._children.insert(index, child)
            self._set_child_order()
        elif self._notebook and \
             len(self._children) > 0 and \
             self._children[-1] == self._notebook.get_trash():
            # append child before trash
            self._children.insert(len(self._children)-1, child)
            self._set_child_order()
        else:
            # append child at end of list
            child._attr["order"] = len(self._children)
            self._children.append(child)

        child._set_dirty(True)

        
    def get_children(self):
        """Returns all children of this node"""
        if self._children is None:
            self._get_children()
        
        return self._children
    
    
    def get_pages(self):
        """Returns the pages in this node"""
        
        if self._children is None:
            self._get_children()
        
        for child in self._children:
            if isinstance(child, NoteBookPage):
                yield child

    def _remove_child(self, child):
        """Remove a child node"""
        if self._children is None:
            self._get_children()
        self._children.remove(child)
    
    
    def notify_change(self, recurse):
        """Notify listeners that node has changed"""
        if self._notebook:
            self._notebook.node_changed.notify([self], recurse)

    def notify_changes(self, nodes, recurse):
        """Notify listeners that several nodes have changed"""
        if self._notebook:
            self._notebook.node_changed.notify(nodes, recurse)
    
    def suppress_change(self, listener=None):
        """Suppress notification of listeners for node changes"""
        if self._notebook:
            self._notebook.node_changed.suppress(listener)

    def resume_change(self, listener=None):
        """Resume notification of listeners for node changes"""        
        if self._notebook:
            self._notebook.node_changed.resume(listener)
    
    def load(self):
        """Load a node from filesystem"""
        self.read_meta_data()
    
    
    def save(self, force=False):
        """Save node if modified (dirty)"""
        
        if (force or self._is_dirty()) and self._valid:
            self.write_meta_data()
            self._set_dirty(False)
            
    def get_data_file(self):
        """Returns filename of data/text/html/etc"""
        return get_page_data_file(self.get_path())


    def read_data_as_plain_text(self):
        """Iterates over the lines of the data file as plain text"""
        
        filename = self.get_data_file()
        infile = open(filename)

        for line in read_data_as_plain_text(infile):
            yield line
            
    
    def write_empty_data_file(self):
        """Initializes an empty data file on file-system"""
        datafile = self.get_data_file()
        
        try:
            out = safefile.open(datafile, "w")
            out.write(BLANK_NOTE)
            out.close()
        except IOError, e:
            raise NoteBookError("Cannot initialize richtext file '%s'" % datafile, e)
        
        
    def get_meta_file(self):
        """Returns the meta file for the node"""
        if self._attr["kind"] == "dir":
            return get_dir_meta_file(self.get_path())
        elif self._attr["kind"] == "page":
            return get_page_meta_file(self.get_path())
        else:
            raise Exception("Unimplemented")
    

    def read_meta_data(self):
        """Read meta data from file-system"""
        self._attr["created_time"] = None
        self._attr["modified_time"] = None    

        try:
            self._meta_parser.read(self, self.get_meta_file())
        except IOError, e:
            raise NoteBookError("Cannot read meta data", e)
        except xmlo.XmlError, e:
            raise NoteBookError("Node meta data is corrupt for note '%s'" %
                                self.get_path(),  e)

        #if self.get_parent() == None:
        #    print "HERE", self._attr

        # set defaults
        if self._attr["created_time"] is None:
            self._attr["created_time"] = get_timestamp()
            self._set_dirty(True)
        if self._attr["modified_time"] is None:
            self._attr["modified_time"] = get_timestamp()
            self._set_dirty(True)

                    
    def write_meta_data(self):
        """Write meta data to file-system"""
        try:
            self._meta_parser.write(self, self.get_meta_file())
        except IOError, e:
            raise NoteBookError("Cannot write meta data", e)
        except xmlo.XmlError, e:
            raise NoteBookError("File format error", e)


    def write_meta_data2(self):
        try:
            out = safefile.open(self.get_meta_file(), "w")
            out.write(XML_HEADER)
            out.write("<node>\n"
                      "<version>2</version>\n")

            for key, val in self._attr.iteritems():
                attr = self._notebook.notebook_attrs.get(key, None)

                if attr is not None:
                    out.write('<attr key="%s">%s</attr>\n' %
                              (key, attr.write(val)))

            out.write("</node>\n")
            out.close()
        except Exception, e:
            raise NoteBookError("Cannot write meta data", e)


    def read_meta_data2(self):

        # prep attrs
        self._attr["created_time"] = None
        self._attr["modified_time"] = None    

    
        try:

            # TODO: move?
            parser = xml.parsers.expat.ParserCreate()
            parser.StartElementHandler = self.__meta_start_element
            parser.EndElementHandler = self.__meta_end_element
            parser.CharacterDataHandler = self.__meta_char_data

            infile = open(self.get_meta_file(), "r")

            self.__meta_body = False
            parser.ParseFile(infile)
            infile.close()
            
        except xml.parsers.expat.ExpatError, e:
            raise NoteBookError("Cannot read meta data", e)
        
        except Exception, e:
            raise NoteBookError("Cannot read meta data", e)

        # set defaults
        if self._attr["created_time"] is None:
            self._attr["created_time"] = get_timestamp()
            self._set_dirty(True)
        if self._attr["modified_time"] is None:
            self._attr["modified_time"] = get_timestamp()
            self._set_dirty(True)


    def __meta_start_element(self, name, attrs):

        # NOTE: assumes no nested tags

        if self.__meta_body:

            if self.__meta_tag is not None:
                raise Exception("corrupt meta file")
                
            self.__meta_tag = name
            self.__meta_attr = attrs
            self.__meta_data = ""

        elif name == "node":
            self.__meta_root = True
        
        
    def __meta_end_element(self, name):

        if name == "node":
            self.__meta_root = False

        if not self.__meta_root:
            return
        
        if self.__meta_tag == "version":
            self._version = int(data)

        elif self.__meta_tag == "attr":
            key = self.__meta_attr.get("key", None)
            if key is not None:
                attr = self._notebook.notebook_attrs.get(key, None)
                if attr is not None:
                    self._attr[key] = attr.read(data)

        # clear state
        self.__meta_tag = None
        self.__meta_attr = None
        self.__meta_data = None
                
        
    def __meta_char_data(self, data):
        """read character data and give it to current tag"""

        if self.__meta_data is not None:
            self.__meta_data += data
            
    

# basic file format for all NoteBookNode's
g_node_meta_data_tags = [
    xmlo.Tag("version",
        getobj=("_version", int),
        set=lambda s: str(NOTEBOOK_FORMAT_VERSION)),
    xmlo.Tag("title", 
        get=lambda s, x: s._attr.__setitem__("title", x),
        set=lambda s: s._attr["title"]),
    xmlo.Tag("order",
        get=lambda s, x: s._attr.__setitem__("order", int(x)),
        set=lambda s: str(s._attr["order"])),
    xmlo.Tag("created_time",
        get=lambda s, x: s._attr.__setitem__("created_time", int(x)),
        set=lambda s: str(s._attr["created_time"])),
    xmlo.Tag("modified_time",
        get=lambda s, x: s._attr.__setitem__("modified_time", int(x)),
        set=lambda s: str(s._attr["modified_time"])),
    xmlo.Tag("info_sort", 
        get=lambda s, x: s._attr.__setitem__("info_sort", int(x)),
        set=lambda s: str(s._attr["info_sort"])),
    xmlo.Tag("info_sort_dir", 
        get=lambda s, x: s._attr.__setitem__("info_sort_dir", int(x)),
        set=lambda s: str(s._attr["info_sort_dir"])),
    xmlo.Tag("expanded",
        get=lambda s, x: s._attr.__setitem__("expanded", bool(int(x))),
        set=lambda s: str(int(s._attr["expanded"]))),
    xmlo.Tag("expanded2",
        get=lambda s, x: s._attr.__setitem__("expanded2", bool(int(x))),
        set=lambda s: str(int(s._attr["expanded2"]))) ]



class NoteBookPage (NoteBookNode):
    """Class that represents a Page in the NoteBook"""
    
    def __init__(self, path, title="", parent=None, notebook=None):
        NoteBookNode.__init__(self, path, title, parent, notebook, kind="page")
        self._meta_parser = g_page_meta_data_parser


class NoteBookDir (NoteBookNode):
    """Class that represents Folders in NoteBook"""
    
    def __init__(self, path, title="", parent=None, notebook=None):
        NoteBookNode.__init__(self, path, title, parent, notebook, kind="dir")
        self._meta_parser = g_dir_meta_data_parser


# TODO: merge dir/page concept

# file format of Pages in NoteBook
g_page_meta_data_parser = xmlo.XmlObject(
    xmlo.Tag("page", tags=
        g_node_meta_data_tags))
            

# file format of Folders in NoteBook
g_dir_meta_data_parser = xmlo.XmlObject(
    xmlo.Tag("node", tags=
        g_node_meta_data_tags))
            

class NoteBookTrash (NoteBookDir):
    """Class represents the Trash Folder in a NoteBook"""

    def __init__(self, name, notebook):
        NoteBookDir.__init__(self, get_trash_dir(notebook.get_path()), 
                             name, parent=notebook, notebook=notebook)
        
    def move(self, parent, index=None):
        """Trash folder only be under root directory"""
        
        if parent == self._notebook:
            assert parent == self._parent
            NoteBookDir.move(self, parent, index)
        else:
            raise NoteBookError("The Trash folder must be a top-level folder.")
    
    def delete(self):
        """Trash folder cannot be deleted"""
        
        raise NoteBookError("The Trash folder cannot be deleted.")


class NoteBookPreferences (object):
    """Preference data structure for a NoteBook"""
    def __init__(self):
        
        self.version = NOTEBOOK_FORMAT_VERSION
        self.default_font = DEFAULT_FONT



# file format for NoteBook preferences
g_notebook_pref_parser = xmlo.XmlObject(
    xmlo.Tag("notebook", tags=[
        xmlo.Tag("version",
            getobj=("version", int),
            set=lambda s: str(s.version)),
        xmlo.Tag("default_font",
            getobj=("default_font", str),
            set=lambda s: s.default_font),
        ]))
    

class NoteBook (NoteBookDir):
    """Class represents a NoteBook"""
    
    def __init__(self, rootdir=None):
        """rootdir -- Root directory of notebook"""
        NoteBookDir.__init__(self, rootdir, notebook=self)
        self.pref = NoteBookPreferences()
        if rootdir is not None:
            self._attr["title"] = os.path.basename(rootdir)
        else:
            self._attr["title"] = None
        self._dirty = set()
        self._trash = None
        self._attr["order"] = 0

        # init notebook attributes
        self.notebook_attrs = {}
        for attr in g_default_attrs:
            self.notebook_attrs[attr.key] = attr
        
        if rootdir:
            self._trash_path = get_trash_dir(self.get_path())
        
        # listeners
        self.node_changed = Listeners()  # node, recurse
        

    def get_trash(self):
        """Returns the Trash Folder for the NoteBook"""
        return self._trash        

    def _set_dirty_node(self, node, dirty):
        """Mark a node to be dirty (needs saving) in NoteBook"""
        if dirty:
            self._dirty.add(node)
        else:
            if node in self._dirty:
                self._dirty.remove(node)
    
    
    def _is_dirty_node(self, node):
        """Returns True if node is dirty (needs saving)"""
        return node in self._dirty
        
    
    def save_needed(self):
        """Returns True if save is needed"""
        return len(self._dirty) > 0
        
        
    def create(self):
        """Initialize NoteBook on the file-system"""
        
        NoteBookDir.create(self)
        os.mkdir(self.get_pref_dir())
        self.write_meta_data()
        self.write_preferences()

    
    def get_root_node(self):
        """Returns the root node of the notebook"""
        return self
    
    
    def load(self, filename=None):
        """Load the NoteBook from the file-system"""
        if filename is not None:
            if os.path.isdir(filename):
                self._set_basename(filename)
            elif os.path.isfile(filename):
                filename = os.path.dirname(filename)
                self._set_basename(filename)
            else:
                raise NoteBookError("Cannot find notebook '%s'" % filename)
            
            self._trash_path = get_trash_dir(self.get_path())
        self.read_meta_data()
        self.read_preferences()
        self.notify_change(True)
    
    
    def save(self, force=False):
        """Recursively save any loaded nodes"""

        if force or self in self._dirty:
            self.write_meta_data()
            self.write_preferences()
        
        self._set_dirty(False)

        if force:
            for node in self.get_children():
                node.save(force=force)
        else:
            for node in list(self._dirty):
                node.save()
        
        self._dirty.clear()
        
    
    def get_children(self):
        """Returns all children of this node"""
        if self._children is None:
            self._get_children()        
            self._init_trash()
        
        return self._children


    def _init_trash(self):
        # ensure trash directory exists
        self._trash = None
        for child in self._children:
            if self.is_trash_dir(child):
                self._trash = child
                break

        # if no trash folder, create it
        if self._trash is None:
            try:
                self._trash = NoteBookTrash(TRASH_NAME, self)
                self._trash.create()
                self._add_child(self._trash)
            except NoteBookError, e:
                raise NoteBookError("Cannot create Trash folder", e)


    
    
    def is_trash_dir(self, child):
        """Returns True if child node is the Trash Folder"""
        return child.get_path() == self._trash_path


    def empty_trash(self):
        """Deletes all nodes under Trash Folder"""

        if self._trash is None:
            self._init_trash()

        for child in reversed(list(self._trash.get_children())):
            child.delete()
        
        
    
    #===============================================
    # preferences
    
    def get_pref_file(self):
        """Gets the NoteBook's preference file"""
        return get_pref_file(self.get_path())
    
    def get_pref_dir(self):
        """Gets the NoteBook's preference directory"""
        return get_pref_dir(self.get_path())
    
    
    def write_preferences(self):
        """Writes the NoteBooks preferences to the file-system"""
        try:
            # ensure preference directory exists
            if not os.path.exists(self.get_pref_dir()):
                os.mkdir(self.get_pref_dir())

            g_notebook_pref_parser.write(self.pref, self.get_pref_file())
        except (IOError, OSError), e:
            raise NoteBookError("Cannot save notebook preferences", e)
        except xmlo.XmlError, e:
            raise NoteBookError("File format error", e)

    
    def read_preferences(self):
        """Reads the NoteBook's preferneces from the file-system"""
        try:
            g_notebook_pref_parser.read(self.pref, self.get_pref_file())
        except IOError, e:
            raise NoteBookError("Cannot read notebook preferences", e)
        except xmlo.XmlError, e:
            raise NoteBookError("Notebook preference data is corrupt", e)

        
        if self.pref.version > NOTEBOOK_FORMAT_VERSION:
            raise NoteBookVersionError(self.pref.version,
                                       NOTEBOOK_FORMAT_VERSION)

