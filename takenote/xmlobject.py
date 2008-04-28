
import sys

import xml.dom.minidom as xmldom
import xml.dom

ELEMENT_NODE = xml.dom.Node.ELEMENT_NODE

import xml.parsers.expat



class Tag (object):
    def __init__(self, name, get=None, set=None, getobj=None, tags=[]):
        self.name = name
        self.get = get
        self.getobj = getobj
        self.set = set
        
        self.tags = {}
        self.tag_list = tags[:]
        for tag in tags:
            self.tags[tag.name] = tag
        
        if self.getobj is not None:
            attr, get = self.getobj
            if get is None:
                self.get = lambda s,x: s.__setattr__(attr, x)
            else:
                self.get = lambda s,x: s.__setattr__(attr, get(x))
        
        
        self.data = None
        
    def write(self, out, obj):
        out.write(self.set(obj))
    
    
    def add(self, tag):
        self.tag_list.append(tag)
        self.tags[tag.name] = tag


class XmlObject (object):
    def __init__(self, *tags):
        self.obj = None
        self.root_tag = Tag("", tags=tags)
        self.current_tags = [self.root_tag]
        
        
        
        
    
    def __start_element(self, name, attrs):
        if len(self.current_tags) > 0:
            last_tag = self.current_tags[-1]
            if name in last_tag.tags:
                self.current_tags.append(last_tag.tags[name])
        
    def __end_element(self, name):
        if len(self.current_tags) > 0:
            if name == self.current_tags[-1].name:
                self.current_tags.pop()
        
    def __char_data(self, data):
        if len(self.current_tags) > 0:
            tag = self.current_tags[-1]
            if tag.get is not None:
                tag.get(self.obj, data)
            
            
    
    def read(self, obj, filename):
        if isinstance(filename, str):
            infile = file(filename)
        else:
            infile = filename
        self.obj = obj
        
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
        self.__write_tag(obj, out, self.root_tag)
        out.write("\n")
        if need_close:
            out.close()
        
        
    def __write_tag(self, obj, out, tag):
        if tag.name != "":
            out.write("<%s>" % tag.name)
        if len(tag.tags) > 0:
            out.write("\n")
            for child_tag in tag.tag_list:
                self.__write_tag(obj, out, child_tag)
        else:
            tag.write(out, obj)
        if tag.name != "":
            out.write("</%s>\n" % tag.name)        



if __name__ == "__main__":

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
                set=lambda s: "%d" % s.hsash_pos)]))

    class Pref (object):
        def __init__(self):
            self.window_size = (0, 0)
            self.window_pos = (0, 0)
            self.vsash_pos = 0
            self.hsash_pos = 0
            
        def read(self, filename):
            parser.read(self, filename)
           
        def write(self, filename):
            parser.write(self, filename)
    
    from rasmus import util
    
    util.tic("run")
    
    for i in xrange(10000):
        pref = Pref()
        pref.read("test/data/notebook/notebook.nbk")
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

