import os, shutil, unittest, traceback, sys, time


import keepnote.gui
from keepnote import notebook as notebooklib
from keepnote.notebook import update

import gtk, gobject


def mk_clean_dir(dirname):
    if os.path.exists(dirname):
        shutil.rmtree(dirname)
    os.makedirs(dirname)
    


class TestCaseWaitDialog (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test1(self):
        """test notebook update from version 1 to 2"""

        app = keepnote.gui.KeepNote()
        app.init()
        win = app.new_window()
        
        start = time.time()

        def func1(task, n=10.0, depth=0):

            if depth == 0: 
                def func2():
                    d = keepnote.gui.dialog_wait.WaitDialog(win)
                    task2 = keepnote.tasklib.Task(lambda t: func1(t, 5.0, 1))
                    d.show("dialog 2", "this is the second dialog", task2)
                    return False
                gobject.idle_add(func2)
            elif depth == 1:
                print "HERE"
                gobject.idle_add(lambda: app.message("Hello", "Hi"))

            t = 0.0
            while t < n and task.is_running():
                task.set_percent(t / n)
                t = time.time() - start
                
        
        d = keepnote.gui.dialog_wait.WaitDialog(win)
        task1 = keepnote.tasklib.Task(func1)
        d.show("dialog 1", "this is the first dialog", task1)

        gtk.main()

        

if __name__ == "__main__":
    unittest.main()



