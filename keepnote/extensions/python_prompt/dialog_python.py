"""

    KeepNote
    Python Shell Dialog

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@alum.mit.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#

# python imports
import os
import sys
import StringIO

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk
import gtk.gdk
import pango


# keepnote imports
import keepnote
from keepnote.gui import Action


def move_to_start_of_line(it):
    """Move a TextIter it to the start of a paragraph"""
    
    if not it.starts_line():
        if it.get_line() > 0:
            it.backward_line()
            it.forward_line()
        else:
            it = it.get_buffer().get_start_iter()
    return it

def move_to_end_of_line(it):
    """Move a TextIter it to the start of a paragraph"""
    it.forward_line()
    return it


class Stream (object):

    def __init__(self, callback):
        self._callback = callback

    def write(self, text):
        self._callback(text)

    def flush(self):
        pass



class PythonDialog (object):
    """Python dialog"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.app = main_window.get_app()

        self.outfile = Stream(self.output_text)
        self.errfile = Stream(lambda t: self.output_text(t, "error"))

        self.error_tag = gtk.TextTag()
        self.error_tag.set_property("foreground", "red")
        self.error_tag.set_property("weight", pango.WEIGHT_BOLD)

        self.info_tag = gtk.TextTag()
        self.info_tag.set_property("foreground", "blue")
        self.info_tag.set_property("weight", pango.WEIGHT_BOLD)

    
    def show(self):

        # setup environment
        self.env = {"app": self.app,
                    "window": self.main_window,
                    "info": self.print_info}

        # create dialog
        self.dialog = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.dialog.connect("delete-event", lambda d,r: self.dialog.destroy())
        self.dialog.ptr = self
        
        self.dialog.set_default_size(400, 400)

        self.vpaned = gtk.VPaned()
        self.dialog.add(self.vpaned)
        self.vpaned.set_position(200)
        
        # editor buffer
        self.editor = gtk.TextView()
        self.editor.connect("key-press-event", self.on_key_press_event)
        f = pango.FontDescription("Courier New")
        self.editor.modify_font(f)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.editor)
        self.vpaned.add1(sw)
        
        # output buffer
        self.output = gtk.TextView()
        self.output.set_wrap_mode(gtk.WRAP_WORD)
        f = pango.FontDescription("Courier New")
        self.output.modify_font(f)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.output)
        self.vpaned.add2(sw)
        
        self.output.get_buffer().tag_table.add(self.error_tag)
        self.output.get_buffer().tag_table.add(self.info_tag)

        self.dialog.show_all()


        self.output_text("Press Ctrl+Enter to execute. Ready...\n", "info")
    

    def on_key_press_event(self, textview, event):
        """Callback from key press event"""
        
        if (event.keyval == gtk.keysyms.Return and
            event.state & gtk.gdk.CONTROL_MASK):
            # execute
            self.execute_buffer()
            return True

        if event.keyval == gtk.keysyms.Return:
            # new line indenting
            self.newline_indent()
            return True


    def newline_indent(self):
        """Insert a newline and indent"""

        buf = self.editor.get_buffer()

        it = buf.get_iter_at_mark(buf.get_insert())
        start = it.copy()
        start = move_to_start_of_line(start)
        line = start.get_text(it)
        indent = []
        for c in line:
            if c in " \t":
                indent.append(c)
            else:
                break
        buf.insert_at_cursor("\n" + "".join(indent))
        

    def execute_buffer(self):
        """Execute code in buffer"""

        buf = self.editor.get_buffer()

        sel = buf.get_selection_bounds()
        if len(sel) > 0:
            # get selection
            start, end = sel
            self.output_text("executing selection:\n", "info")
        else:
            # get all text
            start = buf.get_start_iter()
            end = buf.get_end_iter()
            self.output_text("executing buffer:\n", "info")

        # get text in selection/buffer
        text = start.get_text(end)

        # execute code
        execute(text, self.env, self.outfile, self.errfile)


    def output_text(self, text, mode="normal"):
        """Output text to output buffer"""
        
        buf = self.output.get_buffer()

        # determine whether to follow
        mark = buf.get_insert()
        it = buf.get_iter_at_mark(mark)
        follow = it.is_end()

        # add output text
        if mode == "error":
            buf.insert_with_tags(buf.get_end_iter(), text, self.error_tag)
        elif mode == "info":
            buf.insert_with_tags(buf.get_end_iter(), text, self.info_tag)
        else:
            buf.insert(buf.get_end_iter(), text)
        
        if follow:
            buf.place_cursor(buf.get_end_iter())
            self.output.scroll_mark_onscreen(mark)


    def print_info(self):

        print "COMMON INFORMATION"
        print "=================="
        print

        keepnote.print_runtime_info(sys.stdout)

        print "Open notebooks"
        print "--------------"
        print "\n".join(n.get_path() for n in self.app.iter_notebooks())
        


def execute(code, vars, stdout, stderr):
    """Execute user's python code"""

    __stdout = sys.stdout
    __stderr = sys.stderr
    sys.stdout = stdout
    sys.stderr = stderr
    try:
        exec(code, vars)
    except Exception, e:
        keepnote.log_error(e, sys.exc_info()[2], stderr)
    sys.stdout = __stdout
    sys.stderr = __stderr

