"""

    KeepNote
    Command processing for KeepNote

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@mit.edu>
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

# dbus
try:
    import dbus
    import dbus.bus
    import dbus.service
    import dbus.mainloop.glib
    
except ImportError:
    dbus = None


APP_NAME = "org.ods.rasm.KeepNote"



class SimpleCommandExecutor (object):
    def __init__(self, exec_func):
        self.app = None
        self.exec_func = exec_func

    def set_app(self, app):
        self.app = app

    def execute(self, argv):
        if self.app:
            self.exec_func(self.app, argv)


if dbus:
    class CommandExecutor (dbus.service.Object):
        def __init__(self, bus, path, name, exec_func):
            dbus.service.Object.__init__(self, bus, path, name)
            self.app = None
            self.exec_func = exec_func

        def set_app(self, app):
            self.app = app

        @dbus.service.method(APP_NAME, in_signature='as', out_signature='')
        def execute(self, argv):
            # send command to app

            if self.app:
                self.exec_func(self.app, argv)



def get_command_executor(listen, exec_func):
    
    # setup dbus
    if not dbus or not listen:
        return True, SimpleCommandExecutor(exec_func)

    # setup glib as main loop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    # get bus session
    bus = dbus.SessionBus()

    # test to see if KeepNote is already running
    if bus.request_name(APP_NAME, dbus.bus.NAME_FLAG_DO_NOT_QUEUE) != \
       dbus.bus.REQUEST_NAME_REPLY_EXISTS:
        return True, CommandExecutor(bus, '/', APP_NAME, exec_func)
    else:
        obj = bus.get_object(APP_NAME, "/")
        ce = dbus.Interface(obj, APP_NAME)
        return False, ce


