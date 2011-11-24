"""

    XmlObject

    This module allows concise definitions of XML file formats for python
    objects.

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
import sys
import codecs

# xml imports
import xml.dom.minidom as xmldom
import xml.dom
import xml.parsers.expat
from xml.sax.saxutils import escape

# keepnote imports
from keepnote import safefile


# constants
ELEMENT_NODE = xml.dom.Node.ELEMENT_NODE



class XmlError (StandardError):
    """Error for parsing XML"""
    pass


class Tag (object):
    def __init__(self, name,
                 get=None,
                 set=None,
                 getobj=None,
                 tags=[]):
        self.name = name
        
        self._tag_list = list(tags)
        self._read_data = get
        self._read_data_obj = getobj
        self._write_data = set
        self._object = None
        self._data = []

        # init tag lookup
        self._tags = {}
        for tag in tags:
            self._tags[tag.name] = tag

        # init read_data function
        if self._read_data_obj is not None:
            attr, get = self._read_data_obj
            if get is None:
                self._read_data = lambda s,x: s.__setattr__(attr, x)
            else:
                self._read_data = lambda s,x: s.__setattr__(attr, get(x))
        

    def set_object(self, obj):
        self._object = obj


    def write(self, obj, out):
        # write opening
        if self.name != "":
            out.write("<%s>" % self.name)
        
        if len(self._tags) > 0:
            out.write("\n")
            for child_tag in self._tag_list:
                child_tag.write(obj, out)
        elif self._write_data:
            text = self._write_data(obj)
            if not isinstance(text, basestring):
                raise XmlError("bad text (%s,%s): %s" %
                               (self.name, str(self._object),
                                str(type(text))))
            out.write(escape(text))
        
        if self.name != "":
            out.write("</%s>\n" % self.name)

    def new_tag(self, name):
        tag = self._tags.get(name, None)
        if tag:
            tag.set_object(self._object)
        return tag

    def start_tag(self):
        self._data = []

    def queue_data(self, data):        
        if self._read_data:
            self._data.append(data)

    def end_tag(self):
        
        if self._read_data:
            data = "".join(self._data)
            self._data = []
            
            try:
                self._read_data(self._object, data)
            except Exception, e:
                raise XmlError("Error parsing tag '%s': %s" % (self.name,
                                                               str(e)))

    
    def add(self, tag):
        self._tag_list.append(tag)
        self._tags[tag.name] = tag

        
    


class TagMany (Tag):
    def __init__(self, name, iterfunc, get=None, set=None,
                 before=None,
                 after=None,
                 tags=[]):
        Tag.__init__(self, name,
                     get=None,
                     set=set,
                     tags=tags)
        
        self._iterfunc = iterfunc
        self._read_item = get
        self._write_item = set
        self._beforefunc = before
        self._afterfunc = after
        self._index = 0


    def new_tag(self, name):
        tag = self._tags.get(name, None)
        if tag:
            tag.set_object((self._object, self._index))
        return tag

    def start_tag(self):
        self._data = []
        if self._beforefunc:
            self._beforefunc((self._object, self._index))

    def queue_data(self, data):
        if self._read_item:
            self._data.append(data)

    def end_tag(self):
        if self._read_item:
            data = "".join(self._data)
            self._data = []
            
            try:
                if self._read_item is not None:
                    self._read_item((self._object, self._index), data)
            except Exception, e:
                raise XmlError("Error parsing tag '%s': %s" % (tag.name,
                                                               str(e)))
        
        if self._afterfunc:
            self._afterfunc((self._object, self._index))
        self._index += 1
    
    def write(self, obj, out):
        # write opening
        if len(self._tags)==0:
            assert self._write_item is not None
                
            for i in self._iterfunc(obj):
                out.write("<%s>%s</%s>\n" % (self.name,
                                             escape(self._write_item(obj, i)),
                                             self.name))
        else:
            for i in self._iterfunc(obj):
                out.write("<%s>\n" % self.name)
                for child_tag in self._tag_list:
                    child_tag.write((obj, i), out)
                out.write("</%s>\n" % self.name)


        

class XmlObject (object):
    def __init__(self, *tags):
        self._object = None
        self._root_tag = Tag("", tags=tags)
        self._current_tags = [self._root_tag]
        
    
    def __start_element(self, name, attrs):

        if len(self._current_tags) > 0:
            last_tag = self._current_tags[-1]
            if last_tag:
                new_tag = last_tag.new_tag(name)
                self._current_tags.append(new_tag)
                if new_tag:                
                    new_tag.start_tag()
            
        
    def __end_element(self, name):
                
        if len(self._current_tags) > 0:
            last_tag = self._current_tags.pop()
            if last_tag:
                if last_tag.name == last_tag.name:
                    last_tag.end_tag()
                else:
                    raise XmlError("Malformed XML")            

                
        
    def __char_data(self, data):
        """read character data and give it to current tag"""

        if len(self._current_tags) > 0:
            tag = self._current_tags[-1]
            if tag:
                tag.queue_data(data)
            
            
    
    def read(self, obj, filename):
        if isinstance(filename, basestring):
            infile = open(filename, "r")
        else:
            infile = filename
        self._object = obj
        self._root_tag.set_object(self._object)
        self._current_tags = [self._root_tag]
        
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = self.__start_element
        parser.EndElementHandler = self.__end_element
        parser.CharacterDataHandler = self.__char_data

        try:
            parser.ParseFile(infile)
        except xml.parsers.expat.ExpatError, e:
            raise XmlError("Error reading file '%s': %s" % (filename, str(e)))

        if len(self._current_tags) > 1:
            print [x.name for x in self._current_tags]
            raise XmlError("Incomplete file '%s'" % filename)
        
        infile.close()

            
    def write(self, obj, filename):
        if isinstance(filename, basestring):
            #out = codecs.open(filename, "w", "utf-8")
            out = safefile.open(filename, "w", codec="utf-8")
            #out = file(filename, "w")
            need_close = True
        else:
            out = filename
            need_close = False
        
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        self._root_tag.write(obj, out)
        out.write("\n")
        if need_close:
            out.close()
        
        


if __name__ == "__main__":
    import StringIO

    parser = XmlObject(
        Tag("notebook", tags=[
            Tag("window_size", 
                get=lambda s, x: s.__setattr__("window_size",
                    tuple(map(int,x.split(",")))),
                set=lambda s: "%d,%d" % s.window_size),
            Tag("window_pos",
                getobj=("window_pos", lambda x: 
                    tuple(map(int,x.split(",")))),
                set=lambda s: "%d,%d" % s.window_pos),
            Tag("vsash_pos",
                get=lambda s, x: s.__setattr__("vhash_pos", int(x)),
                set=lambda s: "%d" % s.vsash_pos),
            Tag("hsash_pos",
                get=lambda s, x: s.__setattr__("hsash_pos", int(x)),
                set=lambda s: "%d" % s.hsash_pos),
            Tag("external_apps", tags=[
                TagMany("app",
                        iterfunc=lambda s: range(len(s.apps)),
                        get=lambda (s,i), x: s.apps.append(x),
                        set=lambda (s,i): s.apps[i])]),
            Tag("external_apps2", tags=[
                TagMany("app",
                        iterfunc=lambda s: range(len(s.apps2)),
                        before=lambda s,i: s.apps2.append([None, None]),
                        tags=[Tag("name",
                                  get=lambda (s,i),x: s.apps2[i].__setitem__(0, x),
                                  set=lambda (s,i): s.apps2[i][0]),
                              Tag("prog",
                                  get=lambda (s,i),x: s.apps2[i].__setitem__(1,x),
                                  set=lambda (s,i): s.apps2[i][1])
                        ])
            ]),
        ]))

    class Pref (object):
        def __init__(self):
            self.window_size = (0, 0)
            self.window_pos = (0, 0)
            self.vsash_pos = 0
            self.hsash_pos = 0
            self.apps = []
            self.apps2 = []
            
        def read(self, filename):
            parser.read(self, filename)
           
        def write(self, filename):
            parser.write(self, filename)
    
    from rasmus import util
    
    util.tic("run")

    infile = StringIO.StringIO("""<?xml version="1.0" encoding="UTF-8"?>
       <notebook>
       <window_size>1053,905</window_size>
<window_pos>0,0</window_pos>
<vsash_pos>0</vsash_pos>
<hsash_pos>250</hsash_pos>
<external_apps>
<app>web_browser</app>
<app>image_editor</app>
</external_apps>
<external_apps2>
<app><name>web_browser</name><prog>firefox</prog></app>
<app><name>image_editor</name><prog>gimp</prog></app>
</external_apps2>
       </notebook>
    """)
    
    for i in xrange(1):#0000):
        pref = Pref()
        pref.read(infile)
        pref.write(sys.stdout)
    
    util.toc()
    




'''
def get_dom_children(node):
    """Convenience function for iterating the children of a DOM object"""
    child = node.firstChild
    while child:
        yield child
        child = child.nextSibling
'''

