import os


BLANK_NOTE = "<html><body></body></html>"

#=============================================================================
# NoteBook data structures

class NoteBook (object):
    def __init__(self, rootdir):
        """rootdir -- Root directory of notebook"""
            
        self.root = NoteBookNode(rootdir)
    
    
    def get_root_node(self):
        """Returns the root node of the notebook"""
        return self.root


    def new_page(self, parent_node, name):
        parent_node.new_page(name)


class NoteBookPage (object):
    def __init__(self, path, name=None):
        self.name = name
        self.path = path
        
        if self.name == None:
            self.name = os.path.basename(self.path)
         


class NoteBookNode (object):
    def __init__(self, path, name=None):
        self.path = path
        self.name = name
        
        if self.name == None:
            self.name = os.path.basename(path)
    
    
    def new_page(self, name):
        newpath = os.path.join(self.path, name)
        out = os.open(path, "w")
        out.write(BLANK_NOTE)
        out.close()
        
        return NoteBookPage(newpath)

    
    def rename(self, name):
        path2 = os.path.join(os.path.dirname(self.path), name)
        
        try:
            os.rename(self.path, path2)
            self.name = name
            self.path = path2
        except Exception, e:
            print e
            print "cannot rename page '%s' to '%s'" % (self.path, path2)
    
     
    def get_children(self):
        subdirs = os.listdir(self.path)
        subdirs.sort()
        
        for filename in subdirs:
            path2 = os.path.join(self.path, filename)
            if os.path.isdir(path2):
                yield NoteBookNode(path2)
    
    
    def get_pages(self):
        files = os.listdir(self.path)
        files.sort()
        
        for filename in files:
            path2 = os.path.join(self.path, filename)
            if os.path.isfile(path2):
                yield NoteBookPage(path2)
                
