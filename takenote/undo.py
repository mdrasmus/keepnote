"""

    UndoStack for maintaining undo and redo actions

"""

import sys

from takenote.linked_list import LinkedList




def cat_funcs(funcs):
    """Concatenate a list of functions [f,g,h,...] that take no arguments
       into one function: cat = { lambda: f(); g(); h(); }
    """
    
    funcs = list(funcs)
    def f():
        for func in funcs:
            func()
    return f
            

class UndoStack (object):
    def __init__(self, maxsize=sys.maxint):
        self._undo_actions = LinkedList()
        self._redo_actions = []
        self._action_stack = 0
        self._pending_actions = []
        self._suppress_stack = 0
        self._maxsize = maxsize
    
    
    def do(self, action, undo, execute=True):
        if self._suppress_stack > 0:
            return    
    
        if self._action_stack == 0:
            self._undo_actions.append((action, undo))
            self._redo_actions = []
            if execute:
                action()

            while len(self._undo_actions) > self._maxsize:
                self._undo_actions.pop_front()
        else:
            self._pending_actions.append((action, undo))
            self._redo_actions = []
            if execute:
                action()

    
    def undo(self):
        assert self._action_stack == 0       
        
        if len(self._undo_actions) > 0:
            action, undo = self._undo_actions.pop()
            self.suppress()
            undo()
            self.resume()
            self._redo_actions.append((action, undo))
    
    def redo(self):
        assert self._action_stack == 0
    
        if len(self._redo_actions) > 0:
            action, undo = self._redo_actions.pop()
            self.suppress()            
            action()
            self.resume()
            self._undo_actions.append((action, undo))

            while len(self._undo_actions) > self._maxsize:
                self._undo_actions.pop_front()
    
    def begin_action(self):
        self._action_stack += 1
    
    def end_action(self):
        self._action_stack -= 1
        assert self._action_stack >= 0

        if self._action_stack == 0:
            if len(self._pending_actions) > 0:
                actions, undos = zip(*self._pending_actions)
                
                self._undo_actions.append((cat_funcs(actions), 
                                           cat_funcs(reversed(undos))))
                self._pending_actions = []

                while len(self._undo_actions) > self._maxsize:
                    self._undo_actions.pop_front()

    def suppress(self):
        self._suppress_stack += 1
    
    def resume(self):
        self._suppress_stack -= 1
        assert self._suppress_stack >= 0
    
    def is_suppressed(self):
        return self._suppress_stack > 0
    
    def reset(self):
        self._undo_actions.clear()
        self._redo_actions = []
        self._action_stack = 0
        self._pending_actions = []
        self._suppress_stack = 0

