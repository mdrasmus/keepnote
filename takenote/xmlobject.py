
import sys

import xml.dom.minidom as xmldom
import xml.dom

ELEMENT_NODE = xml.dom.Node.ELEMENT_NODE

import xml.parsers.expat



class Tag (object):
    def __init__(self, name,
                 get=None,
                 set=lambda s: "",
                 getobj=None,
                 tags=[],
                 obj=lambda obj: obj):
        self.name = name
        self.tags = {}
        self.tag_list = tags[:]


        self.get = get
        self.getobj = getobj
        self.set = set
        self.objfunc= obj
        self.obj = None
                
        for tag in tags:
            self.tags[tag.name] = tag
        
        if self.getobj is not None:
            attr, get = self.getobj
            if get is None:
                self.get = lambda s,x: s.__setattr__(attr, x)
            else:
                self.get = lambda s,x: s.__setattr__(attr, get(x))
        
        
        self.data = None

    def set_obj(self, obj):
        self.obj = obj

    def write(self, obj, out):
        # write opening
        if self.name != "":
            out.write("<%s>" % self.name)
        
        if len(self.tags) > 0:
            out.write("\n")
            for child_tag in self.tag_list:
                child_tag.write(obj, out)
        else:
            out.write(self.set(obj))
        
        if self.name != "":
            out.write("</%s>\n" % self.name)

    def new_tag(self, name):
        tag = self.tags.get(name, None)
        if tag:
            tag.set_obj(self.obj)
        return tag

    def start_tag(self):
        pass

    def end_tag(self):
        pass
    
    def add(self, tag):
        self.tag_list.append(tag)
        self.tags[tag.name] = tag

        
    


class TagMany (Tag):
    def __init__(self, name, iterfunc, get=None, set=None, before=None,
                 after=None,
                 tags=[]):
        Tag.__init__(self, name,
                     get=self.__get,
                     set=set,
                     tags=tags)
        
        self.iterfunc = iterfunc
        self.getitem = get
        self.setitem = set
        self.beforefunc = before
        self.afterfunc = after
        self.index = 0

    def __get(self, obj, data):
        if self.getitem is not None:
            self.getitem((obj, self.index), data)

    def new_tag(self, name):
        tag = self.tags.get(name, None)
        tag.obj = (self.obj, self.index)
        return tag

    def start_tag(self):
        if self.beforefunc:
            self.beforefunc(self.obj, self.index)

    def end_tag(self):
        if self.afterfunc:
            self.afterfunc(self.obj, self.index)
        self.index += 1
    
    def write(self, obj, out):
        # write opening
        if len(self.tags)==0:
            assert self.setitem is not None
                
            for i in self.iterfunc(obj):
                out.write("<%s>%s</%s>\n" % (self.name,
                          self.set((obj, i)), self.name))
        else:
            for i in self.iterfunc(obj):
                out.write("<%s>\n" % self.name)
                for child_tag in self.tag_list:
                    child_tag.write((obj, i), out)
                out.write("</%s>\n" % self.name)


        

class XmlObject (object):
    def __init__(self, *tags):
        self.obj = None
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
            if tag.get is not None:
                tag.get(tag.obj, data)
            
            
    
    def read(self, obj, filename):
        if isinstance(filename, str):
            infile = file(filename)
        else:
            infile = filename
        self.obj = obj
        self.root_tag.set_obj(self.obj)
        
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = self.__start_element
        parser.EndElementHandler = self.__end_element
        parser.CharacterDataHandler = self.__char_data        
        parser.ParseFile(infile)
        infile.close()

            
    def write(self, obj, filename):
        if not hasattr(filename, "write"):
            out = file(filename, "w")
            need_close = True
        else:
            out = filename
            need_close = False
        
        out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        #self.__write_tag(obj, out, self.root_tag)
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
                                  get=lambda (s,i),x: s.apps2[i].__setitem__(1, x),
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

