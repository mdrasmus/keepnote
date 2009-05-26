
#=============================================================================
# utilities






class PushIter (object):
    """Wrap an iterator in another iterator that allows one to push new
       items onto the front of the iteration stream"""
    
    def __init__(self, it):
        self._it = iter(it)
        self._queue = []

    def __iter__(self):
        return self
        
    def next(self):
        if len(self._queue) > 0:
            return self._queue.pop()
        else:
            return self._it.next()

    def push(self, item):
        """Push a new item onto the front of the iteration stream"""
        self._queue.append(item)




def compose2(f, g):
    """
    Compose two functions into one

    compose2(f, g)(x) <==> f(g(x))
    """
    return lambda *args, **kargs: f(g(*args, **kargs))
    

def compose(*funcs):
    """Composes two or more functions into one function
    
       example:
       compose(f,g)(x) <==> f(g(x))
    """

    funcs = reversed(funcs)
    f = funcs.next()
    for g in funcs:
        f = compose2(g, f)
    return f

