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
import os, sys, shutil, time, re, traceback, uuid

# xml imports
import xml.dom.minidom as xmldom
import xml.dom
import xml.parsers.expat
from xml.sax.saxutils import escape


# keepnote imports
import keepnote.compat.xmlobject_v3 as xmlo
from keepnote.listening import Listeners
from keepnote.timestamp import \
     DEFAULT_TIMESTAMP_FORMATS, \
     get_timestamp, \
     get_localtime, \
     get_str_timestamp
from keepnote import safefile


# NOTE: the <?xml ?> header is left off to keep it compatiable with IE,
# for the time being.
# constants
BLANK_NOTE = u"""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"><body></body></html>
"""

XML_HEADER = u"""\
<?xml version="1.0" encoding="UTF-8"?>
"""

NOTEBOOK_FORMAT_VERSION = 2
ELEMENT_NODE = 1
NODE_META_FILE = u"node.xml"
PAGE_DATA_FILE = u"page.html"
PLAIN_TEXT_DATA_FILE = u"page.txt"
PREF_FILE = u"notebook.nbk"
NOTEBOOK_META_DIR = u"__NOTEBOOK__"
NOTEBOOK_ICON_DIR = u"icons"
TRASH_DIR = u"__TRASH__"
TRASH_NAME = u"Trash"
DEFAULT_PAGE_NAME = u"New Page"
DEFAULT_DIR_NAME = u"New Folder"
DEFAULT_FONT_FAMILY = "Sans"
DEFAULT_FONT_SIZE = 10
DEFAULT_FONT = "%s %d" % (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)

# content types
CONTENT_TYPE_PAGE = u"text/xhtml+xml"
#CONTENT_TYPE_PLAIN_TEXT = "text/plain"
CONTENT_TYPE_TRASH = u"application/x-notebook-trash"
CONTENT_TYPE_DIR = u"application/x-notebook-dir"
CONTENT_TYPE_UNKNOWN = u"application/x-notebook-unknown"

NULL = object()




#=============================================================================
# filename creation functions

REGEX_SLASHES = re.compile(ur"[/\\]")
REGEX_BAD_CHARS = re.compile(ur"[\?'&<>|`:;]")

def get_valid_filename(filename, default=u"folder"):
    """Converts a filename into a valid one

    Strips bad characters from filename
    """

    filename = re.sub(REGEX_SLASHES, u"-", filename)
    filename = re.sub(REGEX_BAD_CHARS, u"", filename)
    filename = filename.replace(u"\t", " ")
    filename = filename.strip(u" \t.")

    # don't allow files to start with two underscores
    if filename.startswith(u"__"):
        filename = filename[2:]

    # don't allow pure whitespace filenames
    if filename == u"":
        filename = default

    # use only lower case, some filesystems have trouble with mixed case
    filename = filename.lower()

    return filename


def get_unique_filename(path, filename, ext=u"", sep=u" ", number=2,
                        return_number=False, use_number=False):
    """Returns a unique version of a filename for a given directory"""

    if path != "":
        assert os.path.exists(path), path

    # try the given filename
    if not use_number:
        newname = os.path.join(path, filename + ext)
        if not os.path.exists(newname):
            if return_number:
                return (newname, None)
            else:
                return newname

    # try numbered suffixes
    i = number
    while True:
        newname = os.path.join(path, filename + sep + str(i) + ext)
        if not os.path.exists(newname):
            if return_number:
                return (newname, i)
            else:
                return newname
        i += 1


def get_valid_unique_filename(path, filename, ext=u"", sep=u" ", number=2):
    """Returns a valid and unique version of a filename for a given path"""
    return get_unique_filename(path, get_valid_filename(filename),
                               ext, sep, number)


def get_unique_filename_list(filenames, filename, ext=u"", sep=u" ", number=2):
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


def get_node_meta_file(nodepath):
    """Returns the metadata file for a node"""
    return os.path.join(nodepath, NODE_META_FILE)

def get_page_data_file(pagepath):
    """Returns the HTML data file for a page"""
    return os.path.join(pagepath, PAGE_DATA_FILE)

def get_plain_text_data_file(pagepath):
    """Returns the plain text data file for a page"""
    return os.path.join(pagepath, PLAIN_TEXT_DATA_FILE)

def get_pref_file(nodepath):
    """Returns the filename of the notebook preference file"""
    return os.path.join(nodepath, PREF_FILE)

def get_pref_dir(nodepath):
    """Returns the directory of the notebook preference file"""
    return os.path.join(nodepath, NOTEBOOK_META_DIR)

def get_icon_dir(nodepath):
    """Returns the directory of the notebook icons"""
    return os.path.join(nodepath, NOTEBOOK_META_DIR, NOTEBOOK_ICON_DIR)

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

    # TODO: need to handle case when <body> and </body> are on same line

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
# functions


def get_notebook_version(filename):
    """Read the version of a notebook from its preference file"""

    if os.path.isdir(filename):
        filename = get_pref_file(filename)

    pref = NoteBookPreferences()

    try:
        g_notebook_pref_parser.read(pref, filename)
    except IOError, e:
        raise NoteBookError("Cannot read notebook preferences", e)
    except xmlo.XmlError, e:
        raise NoteBookError("Notebook preference data is corrupt", e)

    return pref.version


def new_nodeid():
    return uuid.uuid4()

#=============================================================================
# classes

class NoteBookError (StandardError):
    """Exception that occurs when manipulating NoteBook's"""

    def __init__(self, msg, error=None):
        StandardError.__init__(self)
        self.msg = msg
        self.error = error


    def __str__(self):
        if self.error is not None:
            return repr(self.error) + "\n" + self.msg
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
    """
    A NoteBookAttr is a metadata attribute that can be associated to
    nodes in a NoteBook.
    """

    def __init__(self, name, datatype, key=None, write=None, read=None,
                 default=None):
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

        # default function
        self.default = default


class UnknownAttr (object):
    def __init__(self, value):
        self.value = value



class NoteBookTable (object):
    def __init__(self, name, attrs=[]):
        self.name = name
        self.attrs = list(attrs)

        # TODO: add col widths
        # NoteBooks have tables and attrs



# mapping for old style of saving sort order
_sort_info_backcompat = {"0": "order",
                          "1": "order",
                          "2": "title",
                          "3": "created_time",
                          "4": "modified_time"}
def read_info_sort(key):
    return key
    #return _sort_info_backcompat.get(key, key)


title_attr = NoteBookAttr("Title", unicode, "title")
created_time_attr = NoteBookAttr("Created", int, "created_time", default=get_timestamp)
modified_time_attr = NoteBookAttr("Modified", int, "modified_time", default=get_timestamp)

g_default_attrs = [
    title_attr,
    NoteBookAttr("Content type", unicode, "content_type"),
    NoteBookAttr("Order", int, "order"),
    created_time_attr,
    modified_time_attr,
    NoteBookAttr("Expaned", bool, "expanded"),
    NoteBookAttr("Expanded2", bool, "expanded2"),
    NoteBookAttr("Folder Sort", str, "info_sort", read=read_info_sort),
    NoteBookAttr("Folder Sort Direction", int, "info_sort_dir"),
    NoteBookAttr("Node ID", str, "nodeid", default=new_nodeid),
    NoteBookAttr("Icon", unicode, "icon"),
    NoteBookAttr("Icon Open", unicode, "icon_open")
]


default_notebook_table = NoteBookTable("default", attrs=[title_attr,
                                                         created_time_attr,
                                                         modified_time_attr])



# TODO: parent might be an implict attr


# 1. attrs should be data that is optional (although keepnote has a few
# required entries).
# 2. attrs can appear in listview




class NoteBookNode (object):
    """A general base class for all nodes in a NoteBook"""

    def __init__(self, path, title="", parent=None, notebook=None,
                 content_type=CONTENT_TYPE_DIR):
        self._notebook = notebook
        self._parent = parent
        self._basename = None
        self._children = None
        self._valid = True
        self._version = NOTEBOOK_FORMAT_VERSION
        self._meta = NoteBookNodeMetaData()

        self.clear_attr(title=title, content_type=content_type)

        # TODO: add a mechanism to register implict attrs that in turn do lookup
        # "parent", "nchildren"

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

        # TODO: move to NoteBookPage
        if self._attr["content_type"] == CONTENT_TYPE_PAGE:
            self.write_empty_data_file()



    def get_path(self):
        """Returns the directory path of the node"""

        path_list = []
        ptr = self
        while ptr is not None:
            path_list.append(ptr._basename)
            ptr = ptr._parent
        path_list.reverse()

        return os.path.join(* path_list)


    def get_name_path(self):
        """Returns list of basenames from root to node"""

        path_list = []
        ptr = self
        while ptr is not None:
            path_list.append(ptr._basename)
            ptr = ptr._parent
        path_list.pop()
        path_list.reverse()
        return path_list


    def _set_basename(self, path):
        """Sets the basename directory of the node"""
        if self._parent is None:
            self._basename = path
        elif path is None:
            self._basename = None
        else:
            self._basename = os.path.basename(path)


    def get_version(self):
        """Returns the format version of this node"""
        return self._version


    def get_title(self):
        """Returns the display title of a node"""
        if self._attr["title"] is None:
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

    def allows_children(self):
        """Returns True is this node allows children"""
        return True #self._attr["content_type"] == CONTENT_TYPE_DIR


    def clear_attr(self, title="", content_type=CONTENT_TYPE_DIR):
        """Clear attributes (set them to defaults)"""

        # TODO: generalize this
        # make clear method in attributes
        self._attr = {
            "title": title,
            "content_type": content_type,
            "order": sys.maxint,
            "created_time": None,
            "modified_time": None,
            "expanded": False,
            "expanded2": False,
            "info_sort": "order",
            "info_sort_dir": 1}


    def get_attr(self, name, default=None):
        """Get the value of an attribute"""
        return self._attr.get(name, default)

    def set_attr(self, name, value):
        """Set the value of an attribute"""
        oldvalue = self._attr.get(name, NULL)
        self._attr[name] = value

        # if attr is one that the notebook manages then we are dirty
        # TODO: should have additional test that attr needs to be saved
        # this test is added for the icon_loaded attr, which is not needed to
        # to be saved
        if name in self._notebook.notebook_attrs and \
           value != oldvalue:
            self._set_dirty(True)

    def has_attr(self, name):
        return name in self._attr


    def del_attr(self, name):
        """Delete an attribute"""

        # TODO: check against un-deletable attributes
        if name in self._attr:
            del self._attr[name]


    def iter_attr(self):
        """Iterate through attributes"""
        return self._attr.iteritems()


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
        def walk(node):
            """Uncache children list"""

            if node._children is not None:
                for child in node._children:
                    child._valid = False
                    walk(child)
        walk(self)

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


    def rename(self, title):
        """Renames the title of the node"""

        # do nothing if title is the same
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


    def new_child(self, content_type, title):
        """Add a new node under this node"""

        path = self.get_path()
        newpath = get_valid_unique_filename(path, title)
        node = self._notebook.new_node(content_type, newpath, self, {})

        node.create()
        self._add_child(node)
        node.save(True)
        self.notify_change(True)
        return node


    def get_children(self):
        """Returns all children of this node"""
        if self._children is None:
            self._get_children()

        return self._children


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

            try:
                node = self._notebook.read_node(self, path2)
                if node:
                    self._children.append(node)

            except NoteBookError, e:
                print >>sys.stderr, "error reading", path2
                traceback.print_exception(*sys.exc_info())
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


    def _remove_child(self, child):
        """Remove a child node"""
        if self._children is None:
            self._get_children()
        self._children.remove(child)


    #===============================================
    # listeners

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


    #==============================================
    # input/output

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

        # TODO: make sure to open with UTF-8 encoding

        filename = self.get_data_file()
        infile = open(filename)

        for line in read_data_as_plain_text(infile):
            yield line


    def write_empty_data_file(self):
        """Initializes an empty data file on file-system"""
        datafile = self.get_data_file()

        try:
            out = safefile.open(datafile, "w", codec="utf-8")
            out.write(BLANK_NOTE)
            out.close()
        except IOError, e:
            raise NoteBookError("Cannot initialize richtext file '%s'" % datafile, e)


    def get_meta_file(self):
        """Returns the meta file for the node"""
        return get_node_meta_file(self.get_path())

    def write_meta_data(self):
        self._meta.write(self.get_meta_file(),
                         self,
                         self._notebook.notebook_attrs)

    def read_meta_data(self):
        self._meta.read(self.get_meta_file(),
                        self._notebook.notebook_attrs)
        self.set_meta_data(self._meta.attr)


    def set_meta_data(self, attr):
        self._version = self._meta.attr.get("version", NOTEBOOK_FORMAT_VERSION)

        # set defaults
        if "created_time" not in attr:
            attr["created_time"] = get_timestamp()
            self._set_dirty(True)
        if "modified_time" not in attr:
            attr["modified_time"] = get_timestamp()
            self._set_dirty(True)
        if "nodeid" not in attr or attr["nodeid"].startswith("urn:"):
            attr["nodeid"] = new_nodeid()
            self._set_dirty(True)

        self._attr.update(attr)



class NoteBookPage (NoteBookNode):
    """Class that represents a Page in the NoteBook"""

    def __init__(self, path, title=DEFAULT_PAGE_NAME,
                 parent=None, notebook=None):
        NoteBookNode.__init__(self, path, title, parent, notebook,
                              content_type=CONTENT_TYPE_PAGE)


# TODO: in progress
class NoteBookPlainText (NoteBookNode):
    """Class that represents a plain text Page in the NoteBook"""

    def __init__(self, path, title=DEFAULT_PAGE_NAME,
                 parent=None, notebook=None):
        NoteBookNode.__init__(self, path, title, parent, notebook,
                              content_type="text/plain")

    def get_data_file(self):
        """Returns filename of data/text/html/etc"""
        return get_plain_text_data_file(self.get_path())


    def read_data_as_plain_text(self):
        """Iterates over the lines of the data file as plain text"""

        # TODO: make sure the codec is UTF-8
        return iter(open(self.get_data_file()))


    def write_empty_data_file(self):
        """Initializes an empty data file on file-system"""
        datafile = self.get_data_file()

        try:
            out = safefile.open(datafile, "w", codec="utf-8")
            out.close()
        except IOError, e:
            raise NoteBookError("Cannot initialize richtext file '%s'" % datafile, e)


class NoteBookDir (NoteBookNode):
    """Class that represents Folders in NoteBook"""

    def __init__(self, path, title=DEFAULT_DIR_NAME,
                 parent=None, notebook=None):
        NoteBookNode.__init__(self, path, title, parent, notebook,
                              content_type=CONTENT_TYPE_DIR)



class NoteBookTrash (NoteBookDir):
    """Class represents the Trash Folder in a NoteBook"""

    def __init__(self, name, notebook):
        NoteBookDir.__init__(self, get_trash_dir(notebook.get_path()),
                             name, parent=notebook, notebook=notebook)
        self.set_attr("content_type", CONTENT_TYPE_TRASH)


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
        self.quick_pick_icons = []


# file format for NoteBook preferences
g_notebook_pref_parser = xmlo.XmlObject(
    xmlo.Tag("notebook", tags=[
        xmlo.Tag("version",
            attr=("version", int, str)),
        xmlo.Tag("default_font",
            attr=("default_font", None, None)),
        xmlo.Tag("quick_pick_icons", tags=[
            xmlo.TagMany("icon",
                iterfunc=lambda s: range(len(s.quick_pick_icons)),
                get=lambda (s,i),x:
                    s.quick_pick_icons.append(x),
                set=lambda (s,i): s.quick_pick_icons[i])
        ])
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
        self._init_default_attr()

        # init trash
        if rootdir:
            self._trash_path = get_trash_dir(self.get_path())
        else:
            self._trash_path = None

        # listeners
        self.node_changed = Listeners()  # signature = (node, recurse)

        # add node types
        self._init_default_node_types()


    def _init_default_attr(self):
        """Initialize default notebook attributes"""

        self.notebook_attrs = {}
        for attr in g_default_attrs:
            self.notebook_attrs[attr.key] = attr


    def _init_default_node_types(self):
        """Initialize default node types for notebook"""

        self._node_factory = NoteBookNodeFactory()
        self._node_factory.add_node_type(
            CONTENT_TYPE_DIR,
            lambda path, parent, notebook, attr:
            NoteBookDir(path,
                        parent=parent,
                        notebook=notebook))
        self._node_factory.add_node_type(
            CONTENT_TYPE_PAGE,
            lambda path, parent, notebook, attr:
            NoteBookPage(path,
                         parent=parent,
                         notebook=notebook))
        self._node_factory.add_node_type(
            CONTENT_TYPE_TRASH,
            lambda path, parent, notebook, attr:
            NoteBookTrash(TRASH_NAME, notebook))


    def get_root_node(self):
        """Returns the root node of the notebook"""
        return self

    def get_children(self):
        """Returns all children of this node"""
        if self._children is None:
            self._get_children()
            self._init_trash()

        return self._children

    #===================================================
    # input/output

    def create(self):
        """Initialize NoteBook on the file-system"""

        NoteBookDir.create(self)
        os.mkdir(self.get_pref_dir())
        os.mkdir(self.get_icon_dir())
        self.write_meta_data()
        self.write_preferences()


    def load(self, filename=None):
        """Load the NoteBook from the file-system"""
        if filename is not None:
            filename = unicode(filename)

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


    def read_node(self, parent, path):
        """Read a NoteBookNode"""
        return self._node_factory.read_node(self, parent, path)


    def new_node(self, content_type, path, parent, attr):
        """Create a new NodeBookNode"""
        return self._node_factory.new_node(content_type, path,
                                           parent, self, attr)


    #=====================================
    # trash functions

    def get_trash(self):
        """Returns the Trash Folder for the NoteBook"""
        return self._trash


    def _init_trash(self):
        """Ensures Trash directory exists in a notebook"""

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

    #==============================================
    # icons

    def get_icon_file(self, basename):
        """Lookup icon filename in notebook icon store"""
        filename = os.path.join(self.get_icon_dir(), basename)
        if os.path.exists(filename):
            return filename
        else:
            return None

    def get_icons(self):
        """Returns list of icons in notebook icon store"""

        path = self.get_icon_dir()
        filenames = os.listdir(path)
        filenames.sort()
        return filenames

    def install_icon(self, filename):
        """Installs an icon into the notebook icon store"""

        basename = os.path.basename(filename)
        basename, ext = os.path.splitext(basename)
        newfilename = get_unique_filename(self.get_icon_dir(),
                                          basename, ext, "-")
        shutil.copy(filename, newfilename)

        return os.path.basename(newfilename)


    def install_icons(self, filename, filename_open):
        """Installs an icon into the notebook icon store"""

        basename = os.path.basename(filename)
        basename, ext = os.path.splitext(basename)

        number = 2
        use_number = False
        while True:
            newfilename, number = get_unique_filename(
                self.get_icon_dir(), basename, ext, "-",
                number=number, return_number=True, use_number=use_number)

            # determine open icon filename
            newfilename_open = os.path.join(
                self.get_icon_dir(), basename)
            if number:
                newfilename_open += "-" + str(number)
            else:
                number = 2
            newfilename_open += "-open" + ext

            # see if it already exists
            if os.path.exists(newfilename_open):
                number += 1
                use_number = True
            else:
                # we are done searching for names
                break

        shutil.copy(filename, newfilename)
        shutil.copy(filename_open, newfilename_open)

        return os.path.basename(newfilename), \
               os.path.basename(newfilename_open)

    def uninstall_icon(self, basename):
        """Removes an icon from the notebook icon store"""

        if len(basename) == 0:
            return

        filename = self.get_icon_file(basename)
        if filename:
            os.remove(filename)


    #===============================================
    # preferences

    def get_pref_file(self):
        """Gets the NoteBook's preference file"""
        return get_pref_file(self.get_path())

    def get_pref_dir(self):
        """Gets the NoteBook's preference directory"""
        return get_pref_dir(self.get_path())

    def get_icon_dir(self):
        """Gets the NoteBook's icon directory"""
        return get_icon_dir(self.get_path())


    def write_preferences(self):
        """Writes the NoteBooks preferences to the file-system"""
        try:
            # ensure preference directory exists
            if not os.path.exists(self.get_pref_dir()):
                os.mkdir(self.get_pref_dir())

            # ensure icon directory exists
            if not os.path.exists(self.get_icon_dir()):
                os.mkdir(self.get_icon_dir())

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



#
# TODO: perhaps factory and metadata reader should be combined?
#

class NoteBookNodeFactory (object):
    """
    This is a factory class that creates NoteBookNode's.
    """

    def __init__(self):
        self._makers = {}
        self._meta = NoteBookNodeMetaData()


    def add_node_type(self, content_type, make_func):
        """
        Adds a new node content_type to the factory.
        Enables factory to build nodes of the given type by calling the
        given function 'make_func'.

        make_func must have the signature:
           make_func(path, parent, notebook, attr_dict)
        """

        self._makers[content_type] = make_func


    def read_node(self, notebook, parent, path):
        """Reads a node from disk"""

        filename = os.path.basename(path)
        metafile = get_node_meta_file(path)
        node = None

        if os.path.exists(metafile):
            self._meta.read(metafile, notebook.notebook_attrs)

            # NOTE: node can be None
            node = self.new_node(self._meta.attr.get("content_type",
                                                     CONTENT_TYPE_DIR),
                                 path, parent, notebook, self._meta.attr)
        else:
            # ignore directory, not a NoteBook directory
            pass

        return node


    def new_node(self, content_type, path, parent, notebook, attr):
        """Creates a new node given a content_type"""

        maker = self._makers.get(content_type, None)
        if maker:
            node = maker(path, parent, notebook, attr)
            node.set_meta_data(attr)
            return node
        else:
            # TODO: return unknown node here
            return None



class NoteBookNodeMetaData (object):
    """Reads and writes metadata for NoteBookNode objects"""

    def __init__(self):
        self.attr = {}
        self.attr_unknown = {}
        self._notebook_attrs = {}

        self._parser = None
        self.__meta_root = False
        self.__meta_data = None
        self.__meta_tag = None


    def write(self, filename, node, notebook_attrs):

        try:
            out = safefile.open(filename, "w", codec="utf-8")
            out.write(XML_HEADER)
            out.write("<node>\n"
                      "<version>%s</version>\n" % node.get_version())

            for key, val in node.iter_attr():
                attr = notebook_attrs.get(key, None)

                if attr is not None:
                    out.write('<attr key="%s">%s</attr>\n' %
                              (key, escape(attr.write(val))))
                elif key == "version":
                    # skip version attr
                    pass
                elif isinstance(val, UnknownAttr):
                    # write unknown attrs if they are strings
                    out.write('<attr key="%s">%s</attr>\n' %
                              (key, escape(val.value)))
                else:
                    # drop attribute
                    pass

            out.write("</node>\n")
            out.close()
        except Exception, e:
            print e
            raise NoteBookError("Cannot write meta data", e)


    def read(self, filename, notebook_attrs):

        self._notebook_attrs = notebook_attrs
        self.attr = {}
        self.attr_unknown = {}

        try:
            self.__meta_root = False
            self.__meta_data = None
            self.__meta_tag = None

            self._parser = xml.parsers.expat.ParserCreate()
            self._parser.StartElementHandler = self.__meta_start_element
            self._parser.EndElementHandler = self.__meta_end_element
            self._parser.CharacterDataHandler = self.__meta_char_data

            infile = open(filename, "rb")
            self._parser.ParseFile(infile)
            infile.close()

        except xml.parsers.expat.ExpatError, e:
            raise NoteBookError("Cannot read meta data", e)

        except Exception, e:
            raise NoteBookError("Cannot read meta data", e)



    def __meta_start_element(self, name, attrs):

        # NOTE: assumes no nested tags

        if self.__meta_root:
            if self.__meta_tag is not None:
                raise Exception("corrupt meta file")

            self.__meta_tag = name
            self.__meta_attr = attrs
            self.__meta_data = ""

        elif name == "node":
            self.__meta_root = True


    def __meta_end_element(self, name):

        try:
            if name == "node":
                self.__meta_root = False

            if not self.__meta_root:
                return

            if self.__meta_tag == "version":
                self.attr["version"] = int(self.__meta_data)

            elif self.__meta_tag == "attr":
                key = self.__meta_attr.get("key", None)
                if key is not None:
                    attr = self._notebook_attrs.get(key, None)
                    if attr is not None:
                        self.attr[key] = attr.read(self.__meta_data)
                    else:
                        # unknown attribute is read as a UnknownAttr
                        self.attr[key] = UnknownAttr(self.__meta_data)

            # clear state
            self.__meta_tag = None
            self.__meta_attr = None
            self.__meta_data = None
        except Exception:
            # TODO: I could record parsing exceptions here
            raise


    def __meta_char_data(self, data):
        """read character data and give it to current tag"""

        if self.__meta_data is not None:
            self.__meta_data += data


