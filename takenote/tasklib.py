import sys, threading


from takenote import listening


STOPPED = 0
RUNNING = 1
STOPPING = 2


class Task (object):

    def __init__(self, func=None):
        self._lock = threading.Lock()
        self._messages = []
        self._percent = None
        self._state = STOPPED
        self._result = None
        self._func = func
        self._exc_info = (None, None, None)
        self._aborted = False
        self._proc = None
        
        self.change_event = listening.Listeners()

    def lock(self):
        self._lock.acquire()

    def unlock(self):
        self._lock.release()
        

    def set_result(self, result):
        self._lock.acquire()
        self._result = result
        self._lock.release()

        self.change_event.notify()


    def get_result(self):
        self._lock.acquire()
        r = self._result
        self._lock.release()
        return r
    

    def set_percent(self, percent):
        self._lock.acquire()
        self._percent = percent
        self._lock.release()

        self.change_event.notify()

    def get_percent(self):
        return self._percent
    

    def set_message(self, message):
        self._lock.acquire()
        self._messages.append(message)        
        self._lock.release()

        self.change_event.notify()

    def get_messages(self, clear=True):
        self._lock.acquire()
        
        messages = list(self._messages)
        if clear:
            self._messages = []
            
        self._lock.release()
        return messages

    def exc_info(self):
        self._lock.acquire()
        e = self._exc_info
        self._lock.release()
        return e
    

    def run(self, new_thread=True):
        self._lock.acquire()
        self._state = RUNNING
        self._aborted = False
        self._exc_info = (None, None, None)
        self._proc = None

        # run function
        if self._func:
            if new_thread:
                self._proc = threading.Thread(target=self._new_thread)
            else:
                self._func(self)
        
        self._lock.release()

        if self._proc:
            self._proc.start()


    def join(self):
        if self._proc:
            self._proc.join()
            

    def _new_thread(self):
        try:            
            self._func(self)
            self.finish()
            
        except Exception, e:
            
            self._lock.acquire()
            self._exc_info = sys.exc_info()
            self._aborted = True
            self._state = STOPPED
            self._lock.release()

            self.change_event.notify()
                


    def stop(self):
        """Request that the task be stopped"""
        self._lock.acquire()
        if self._state == RUNNING:
            self._state = STOPPING
            self._aborted = True
        self._lock.release()

        self.change_event.notify()

    def finish(self):
        """Called by task to acknowledge that task is completely stopped"""
        self._lock.acquire()
        self._state = STOPPED
        self._lock.release()
        
        self.change_event.notify()

    def is_stopped(self):
        self._lock.acquire()
        s = self._state == STOPPED
        self._lock.release()
        return s

    def is_running(self):
        self._lock.acquire()
        s = self._state == RUNNING
        self._lock.release()
        return s

    def get_state(self):
        self._lock.acquire()
        s = self._state
        self._lock.release()
        return s

    def aborted(self):
        self._lock.acquire()
        a = self._aborted
        self._lock.release()
        return a

