"""
    KeepNote
    extended plist module

    Apple's property list xml serialization

    - added null type
"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.elementtree.ElementTree as ET
from StringIO import StringIO
import base64
import datetime
import re
import sys
from xml.sax.saxutils import escape

try:
    from .orderdict import OrderDict
except (ImportError, ValueError):
    OrderDict = dict


class Data (object):
    def __init__(self, text):
        self.text = text


# date format:
# ISO 8601 (in particular, YYYY '-' MM '-' DD 'T' HH ':' MM ':' SS 'Z'.
# Smaller units may be omitted with a loss of precision


_unmarshallers = {
    # collections
    "array": lambda x: [v.text for v in x],
    "dict": lambda x: OrderDict(
        (x[i].text, x[i+1].text) for i in range(0, len(x), 2)),
    "key": lambda x: x.text or u"",

    # simple types
    "string": lambda x: x.text or u"",
    "data": lambda x: Data(base64.decodestring(x.text or u"")),
    "date": lambda x: datetime.datetime(*map(int, re.findall("\d+", x.text))),
    "true": lambda x: True,
    "false": lambda x: False,
    "real": lambda x: float(x.text),
    "integer": lambda x: int(x.text),
    "null": lambda x: None

}


def load(infile=sys.stdin):
    parser = ET.iterparse(infile)

    for action, elem in parser:
        unmarshal = _unmarshallers.get(elem.tag)
        if unmarshal:
            data = unmarshal(elem)
            elem.clear()
            elem.text = data
        elif elem.tag != "plist":
            raise IOError("unknown plist type: %r" % elem.tag)

    return parser.root.text


def loads(string):
    return load(StringIO(string))


def load_etree(elm):
    for child in elm:
        load_etree(child)

    unmarshal = _unmarshallers.get(elm.tag)
    if unmarshal:
        data = unmarshal(elm)
        elm.clear()
        elm.text = data
    elif elm.tag != "plist":
        raise IOError("unknown plist type: %r" % elm.tag)

    return elm.text


def dump(elm, out=sys.stdout, indent=0, depth=0, suppress=False):

    if indent and not suppress:
        out.write(" " * depth)

    if isinstance(elm, dict):
        out.write(u"<dict>")
        if indent:
            out.write(u"\n")
        for key, val in elm.iteritems():
            if indent:
                out.write(" " * (depth + indent))
            out.write(u"<key>%s</key>" % key)
            dump(val, out, indent, depth+indent, suppress=True)
        if indent:
            out.write(" " * depth)
        out.write(u"</dict>")

    elif isinstance(elm, (list, tuple)):
        out.write(u"<array>")
        if indent:
            out.write(u"\n")
        for item in elm:
            dump(item, out, indent, depth+indent)
        if indent:
            out.write(" " * depth)
        out.write(u"</array>")

    elif isinstance(elm, basestring):
        out.write(u"<string>%s</string>" % escape(elm))

    elif isinstance(elm, bool):
        if elm:
            out.write(u"<true/>")
        else:
            out.write(u"<false/>")

    elif isinstance(elm, (int, long)):
        out.write(u"<integer>%d</integer>" % elm)

    elif isinstance(elm, float):
        out.write(u"<real>%f</real>" % elm)

    elif elm is None:
        out.write(u"<null/>")

    elif isinstance(elm, Data):
        out.write(u"<data>")
        base64.encode(StringIO(elm), out)
        out.write(u"</data>")

    elif isinstance(elm, datetime.datetime):
        raise Exception("not implemented")

    else:
        raise Exception("unknown data type '%s' for value '%s'" %
                        (str(type(elm)), str(elm)))

    if indent:
        out.write(u"\n")


def dumps(elm, indent=0):
    s = StringIO()
    dump(elm, s, indent)
    return s.getvalue()


def dump_etree(elm):
    if isinstance(elm, dict):
        elm2 = ET.Element("dict")
        for key, val in elm.iteritems():
            key2 = ET.Element("key")
            key2.text = key
            elm2.append(key2)
            elm2.append(dump_etree(val))

    elif isinstance(elm, (list, tuple)):
        elm2 = ET.Element("array")
        for item in elm:
            elm2.append(dump_etree(item))

    elif isinstance(elm, basestring):
        elm2 = ET.Element("string")
        elm2.text = elm

    elif isinstance(elm, bool):
        if elm:
            elm2 = ET.Element("true")
        else:
            elm2 = ET.Element("false")

    elif isinstance(elm, int):
        elm2 = ET.Element("integer")
        elm2.text = str(elm)

    elif isinstance(elm, float):
        elm2 = ET.Element("real")
        elm2.text = str(elm)

    elif elm is None:
        elm2 = ET.Element("null")

    elif isinstance(elm, Data):
        elm2 = ET.Element("data")
        elm2.text = base64.encodestring(elm)

    elif isinstance(elm, datetime.datetime):
        raise Exception("not implemented")

    else:
        raise Exception("unknown data type '%s' for value '%s'" %
                        (str(type(elm)), str(elm)))

    return elm2
