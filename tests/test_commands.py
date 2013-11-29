import os, shutil, unittest, thread, threading, traceback, sys, time

# keepnote imports
import keepnote
from keepnote import commands



class Commands (unittest.TestCase):
    
    def setUp(self):      
        pass


    def test1(self):
        args = ['a b', 'c d']
        args2 = commands.parse_command(commands.format_command(args))
        
        self.assertEquals(args, args2)


if __name__ == "__main__":
    unittest.main()

