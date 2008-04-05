"""

    UndoStack for maintaining undo and redo actions

"""


class UndoStack (object):
    def __init__(self):
        self.undo_actions = []
        self.redo_actions = []
        self.action_stack = 0
        self.pending_actions = []
        self.suppress_stack = 0
    
    
    def do(self, action, undo, execute=True):
        if self.suppress_stack > 0:
            return    
    
        if self.action_stack == 0:
            self.undo_actions.append((action, undo))
            self.redo_actions = []
            if execute:
                action()
        else:
            self.pending_actions.append((action, undo))
            self.redo_actions = []
            if execute:
                action()
    
    def undo(self):
        assert self.action_stack == 0       
        
        if len(self.undo_actions) > 0:
            action, undo = self.undo_actions.pop()
            self.suppress()
            undo()
            self.resume()
            self.redo_actions.append((action, undo))
    
    def redo(self):
        assert self.action_stack == 0
    
        if len(self.redo_actions) > 0:
            action, undo = self.redo_actions.pop()
            self.suppress()            
            action()
            self.resume()
            self.undo_actions.append((action, undo))
    
    def begin_action(self):
        self.action_stack += 1
    
    def end_action(self):
        self.action_stack -= 1
        
        def make_call(funcs):
            def f():
                for func in funcs:
                    func()
            return f
        
        if self.action_stack == 0:
            if len(self.pending_actions) > 0:
                actions, undos = zip(*self.pending_actions)
                
                self.undo_actions.append((make_call(actions), 
                                          make_call(undos)))
                self.pending_actions = []

    def suppress(self):
        self.suppress_stack += 1
    
    def resume(self):
        self.suppress_stack -= 1
        assert self.suppress_stack >= 0
    
    def reset(self):
        self.undo_actions = []
        self.redo_actions = []
        self.action_stack = 0
        self.pending_actions = []
        self.suppress_stack = 0

