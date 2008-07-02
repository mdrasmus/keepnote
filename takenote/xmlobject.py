"""

    XmlObject

    The modules allows concise definitions of XML file formats for python
    objects.

"""


# python imports
import sys
import codecs

# xml imports
import xml.dom.minidom as xmldom
import xml.dom
import xml.parsers.expat
from xml.sax.saxutils import escape


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
                 tags=[],
                 obj=lambda obj: obj):
        self.name = name
        self.tags = {}
        self.tag_list = tags[:]


        self._read_data = get
        self._read_data_obj = getobj
        self._write_data = set
        self._object = None
        self._data = []
                
        for tag in tags:
            self.tags[tag.name] = tag
        
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
        
        if len(self.tags) > 0:
            out.write("\n")
            for child_tag in self.tag_list:
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
        tag = self.tags.get(name, None)
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
                raise XmlError("Error parsing tag '%s': %s" % (tag.name,
                                                               str(e)))

    
    def add(self, tag):
        self.tag_list.append(tag)
        self.tags[tag.name] = tag

        
    


class TagMany (Tag):
    def __init__(self, name, iterfunc, get=None, set=None,
                 before=None,
                 after=None,
                 tags=[]):
        Tag.__init__(self, name,
                     get=None,
                     set=set,
                     tags=tags)
        
        self.iterfunc = iterfunc
        self._read_item = get
        self._write_item = set
        self.beforefunc = before
        self.afterfunc = after
        self.index = 0


    def new_tag(self, name):
        tag = self.tags.get(name, None)
        tag.set_object((self._object, self.index))
        return tag

    def start_tag(self):
        self._data = []
        if self.beforefunc:
            self.beforefunc((self._object, self.index))

    def queue_data(self, data):
        if self._read_item:
            self._data.append(data)

    def end_tag(self):
        if self._read_item:
            data = "".join(self._data)
            self._data = []
            
            try:
                if self._read_item is not None:
                    self._read_item((self._object, self.index), data)
            except Exception, e:
                raise XmlError("Error parsing tag '%s': %s" % (tag.name,
                                                               str(e)))
        
        if self.afterfunc:
            self.afterfunc((self._object, self.index))
        self.index += 1
    
    def write(self, obj, out):
        # write opening
        if len(self.tags)==0:
            assert self._write_item is not None
                
            for i in self.iterfunc(obj):
                out.write("<%s>%s</%s>\n" % (self.name,
                                             escape(self._write_item(obj, i)),
                                             self.name))
        else:
            for i in self.iterfunc(obj):
                out.write("<%s>\n" % self.name)
                for child_tag in self.tag_list:
                    child_tag.write((obj, i), out)
                out.write("</%s>\n" % self.name)


        

class XmlObject (object):
    def __init__(self, *tags):
        self._object = None
        self.root_tag = Tag("", tags=tags)
        self.current_tags = [self.root_tag]
        
    
    def __start_element(self, name, attrs):
        if len(self.current_tags) > 0:
            last_tag = self.current_tags[-1]
            new_tag = last_tag.new_tag(name)
            if new_tag:
                self.current_tags.append(new_tag)
                new_tag.start_tag()
        
    def __end_element(self, name):
        if len(self.current_tags) > 0:
            if name == self.current_tags[-1].name:
                tag = self.current_tags.pop()
                tag.end_tag()
                
        
    def __char_data(self, data):
        """read character data and give it to current tag"""

        if len(self.current_tags) > 0:
            tag = self.current_tags[-1]
            tag.queue_data(data)
            
            
    
    def read(self, obj, filename):
        if isinstance(filename, basestring):
            infile = open(filename, "r")
        else:
            infile = filename
        self._object = obj
        self.root_tag.set_object(self._object)
        
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = self.__start_element
        parser.EndElementHandler = self.__end_element
        parser.CharacterDataHandler = self.__char_data

        try:
            parser.ParseFile(infile)
        except xml.parsers.expat.ExpatError, e:
            raise XmlError("Error reading file '%s': %s" % (filename, str(e)))

        infile.close()

            
    def write(self, obj, filename):
        if isinstance(filename, basestring):
            out = codecs.open(filename, "w", "utf-8")
            #out = file(filename, "w")
            need_close = True
        else:
            out = filename
            need_close = False
        
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        self.root_tag.write(obj, out)
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

