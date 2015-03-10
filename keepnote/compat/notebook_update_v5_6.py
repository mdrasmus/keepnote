"""

    KeepNote
    updating notebooks

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

import os,sys
import keepnote
from keepnote import safefile, plist
from keepnote.timestamp import get_timestamp
import xml.etree.cElementTree as ET


def new_nodeid():
    """Generate a new node id"""
    return unicode(uuid.uuid4())


def iter_child_node_paths(path):
    """Given a path to a node, return the paths of the child nodes"""

    children = os.listdir(path)

    for child in children:
        child_path = os.path.join(path, child)
        if os.path.isfile(os.path.join(child_path, u"node.xml")):
            yield child_path


class AttrDef (object):
    """
    A AttrDef is a metadata attribute that can be associated to
    nodes in a NoteBook.
    """

    def __init__(self, key, datatype, name, default=None):

        self.name = name
        self.datatype = datatype
        self.key = key

        # default function
        if default is None:
            self.default = datatype
        else:
            self.default = default

        # writer function
        if datatype == bool:
            self.write = lambda x: unicode(int(x))
        else:
            self.write = unicode

        # reader function
        if datatype == bool:
            self.read = lambda x: bool(int(x))
        else:
            self.read = datatype


class UnknownAttr (object):
    """A value that belongs to an unknown AttrDef"""

    def __init__(self, value):
        self.value = value


g_default_attr_defs = [
    AttrDef("nodeid", unicode, "Node ID", default=new_nodeid),
    AttrDef("content_type", unicode, "Content type",
            default=lambda: CONTENT_TYPE_DIR),
    AttrDef("title", unicode, "Title"),
    AttrDef("order", int, "Order", default=lambda: sys.maxint),
    AttrDef("created_time", int, "Created time", default=get_timestamp),
    AttrDef("modified_time", int, "Modified time", default=get_timestamp),
    AttrDef("expanded", bool, "Expaned", default=lambda: True),
    AttrDef("expanded2", bool, "Expanded2", default=lambda: True),
    AttrDef("info_sort", unicode, "Folder sort", default=lambda: "order"),
    AttrDef("info_sort_dir", int, "Folder sort direction", default=lambda: 1),
    AttrDef("icon", unicode, "Icon"),
    AttrDef("icon_open", unicode, "Icon open"),
    AttrDef("payload_filename", unicode, "Filename"),
    AttrDef("duplicate_of", unicode, "Duplicate of")
]

g_attr_defs_lookup = dict((attr.key, attr) for attr in g_default_attr_defs)


def read_attr_v5(filename, attr_defs=g_attr_defs_lookup):

    attr = {}

    tree = ET.ElementTree(file=filename)

    # check root
    root = tree.getroot()
    if root.tag != "node":
        raise Except("Root tag is not 'node'")

    version = int(root.find("version").text)
    if version >= 6:
        # check if node somehow already converted
        if root.find("dict"):
            return
        # try to read with old format anyways

    # iterate children
    for child in root:
        if child.tag == "version":
            attr["version"] = int(child.text)
        elif child.tag == "attr":
            key = child.get("key", None)
            if key is not None:
                attr_parser = attr_defs.get(key, None)
                if attr_parser is not None:
                    attr[key] = attr_parser.read(child.text)
                else:
                    # unknown attribute is read as a UnknownAttr
                    attr[key] = child.text

    return attr


def write_attr_v6(filename, attr):
    out = safefile.open(filename, "w", codec="utf-8")
    out.write(u'<?xml version="1.0" encoding="UTF-8"?>\n'
              u'<node>\n'
              u'<version>%d</version>\n' % attr["version"])
    plist.dump(attr, out, indent=2, depth=0)
    out.write(u'</node>\n')
    out.close()


def convert_node_attr(filename, filename2, attr_defs=g_attr_defs_lookup):
    """Convert a node.xml file from version 5 to 6"""

    keepnote.log_message("converting '%s'...\n" % filename2)

    try:
        attr = read_attr_v5(filename, attr_defs)
        attr["version"] = 6
        write_attr_v6(filename2, attr)
    except Exception, e:
        keepnote.log_error("cannot convert %s: %s\n" % (filename, str(e)),
                           sys.exc_info()[2])




def update(filename):
    filename = unicode(filename)

    def walk(path):
        nodepath = os.path.join(path, u"node.xml")
        convert_node_attr(nodepath, nodepath)
        for path2 in iter_child_node_paths(path):
            walk(path2)

    walk(filename)

    preffile = os.path.join(filename, u"notebook.nbk")
    etree = ET.ElementTree(file=preffile)
    root = etree.getroot()
    root.find("version").text = "6"
    etree.write(preffile, encoding="utf-8")




