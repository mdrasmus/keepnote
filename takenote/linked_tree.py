"""
   A tree implemented with linked lists
"""

class LinkedTreeNode (object):
    """A node in a linked list tree"""

    def __init__(self):
        self._parent = None
        self._next = None
        self._prev = None
        self._child = None

        # NOTE: if first child, self._prev = last sibling

    def get_parent(self):
        """Returns parent"""
        return self._parent

    def __iter__(self):
        """Iterate over children"""
        node = self._child
        while node:
            yield node
            node = node._next

    def get_children_list(self):
        """Returns a list of the children"""
        return list(self)

    def num_children(self):
        """Returns the number of children"""
        n = 0
        for child in self:
            n += 1
        return n

    def first_child(self):
        """Return first child or None"""
        return self._child

    def has_children(self):
        """Returns True if node has children"""
        return self._child is not None

    def last_child(self):
        """Returns last child or None"""
        if not self._child:
            return None
        else:
            return self._child._prev

    def next_sibling(self):
        """Returns next sibling or None"""
        return self._next

    def prev_sibling(self):
        """Returns previous sibling or None"""
        if self._parent and self._parent._child is not self:
            return self._prev
        else:
            return None
            

    def append_child(self, child):
        """Append child to end of sibling list"""

        if self._child is None:
            # add first child
            self._child = child
            child._prev = child
        else:
            # append child to end of sibling list
            last = self._child._prev
            last._next = child
            child._prev = last
            self._child._prev = child

        child._next = None
        child._parent = self

    def prepend_child(self, child):
        """Prepend child to begining of sibling list"""

        if self._child is None:
            # add first child
            self._child = child
            child._prev = child
            child._next = None
        else:
            # prepend to begining of sibling list
            first = self._child
            child._next = first
            child._prev = first._prev            
            first._prev = child
            self._child = child

        child._parent = self

    def remove_child(self, child):
        """Remove child from Node"""
        assert child._parent is self
        self.child.remove()

    def remove(self):
        """Remove from parent"""
        
        if self._next:
            # setup next sibling
            self._next._prev = self._prev
        if self._parent._child is not self:
            # setup prev sibling, if they exist
            self._prev._next = self._next
        else:
            # find new first child
            self._parent._child = self._next

        # remove old links
        self._parent = None
        self._next = None
        self._prev = None
    
        

