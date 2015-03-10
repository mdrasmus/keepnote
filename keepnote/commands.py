"""

    KeepNote
    Command processing for KeepNote

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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

# python libs
import errno
import os
import random
import socket
import sys
import thread

# keepnote libs
import keepnote


# constants
KEEPNOTE_HEADER = "keepnote\n"
#KEEPNOTE_EOF = "\x00"
#KEEPNOTE_ESCAPE = "\xff"


# TODO: add unicode support

# TODO: ensure commands are executed in order, but don't allow malicious
# process to DOS main process (may be minor issue)

#=============================================================================
# lock file

def get_lock_file(lockfile):
    """
    Try to acquire a lock file
    Returns (acquire, fd) where 'acquire' is True if the lock is acquired and
    'fd' is the file descriptor of the lock file.
    """
    acquire = False

    while True:
        try:
            # try to create file with exclusive access
            fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0600)

            # creation succeeded, we have the lock
            acquire = True
            break

        except OSError, e:
            if e.errno != errno.EEXIST:
                # unknown error, re-raise
                raise

            try:
                # lock already exists (i.e. held by someone else)
                # try to open it in read only mode
                fd = os.open(lockfile, os.O_RDONLY)
                acquire = False
                break

            except OSError, e:
                if e.errno != errno.ENOENT:
                    # unknown error, re-raise
                    raise

                # The lock file disapeared between the two open attempts.
                # Loop and try again.

    return acquire, fd


def write_lock_file(fd, port, passwd):
    """Write a KeepNote lock file"""
    os.write(fd, "%d:%s" % (port, passwd))


def read_lock_file(fd):
    """Parse a KeepNote lock file"""
    text = os.read(fd, 1000)
    port, passwd = text.split(":")
    port = int(port)
    return port, passwd


def make_passwd():
    """Generate a random password"""
    return str(random.randint(0, 1000000))


#=============================================================================
# sockets

def open_socket(port=None, start_port=4000, end_port=10000, tries=10):
    """
    Open a new socket to listen for new connections.
    This function makes multiple attempts and can possibly try random
    port numbers.
    """
    s = socket.socket(socket.AF_INET)

    for i in range(tries):
        # choose port
        if port is None:
            port2 = random.randint(start_port, end_port)
        else:
            port2 = port

        try:
            s.bind(("localhost", port2))
            s.listen(1)
            break
        except socket.error, e:
            print >>sys.stderr, "could not open socket:", str(e)
            port2 = None

    if port2 is None:
        s.close()
        s = None

    return s, port2


def listen_commands(sock, connfunc, args):
    """
    Listen for new connections and handle them with new threads

    sock     -- socket to listen on
    connfunc -- function to call in new thread
                must take arguments (conn, addr, *args)
    args     -- tuple of arguments to pass to connfunc
    """
    while True:
        try:
            conn, addr = sock.accept()
        except socket.error:
            continue

        thread.start_new_thread(connfunc, (conn, addr) + args)


def process_connection(conn, addr, passwd, execfunc):
    """
    Process a connection
    conn     -- connection to other process
    addr     -- address of other process
    passwd   -- password required to accept connect
    execfunc -- function to call with command
    """

    try:
        connfile = conn.makefile("rw")
        connfile.write(KEEPNOTE_HEADER)
        connfile.flush()
        passwd2 = connfile.readline().rstrip("\n")
        command = connfile.readline().rstrip("\n")

        # ensure password matches
        if passwd2 != passwd:
            # password failed, close connection
            conn.close()
            return

        # parse command and execute
        try:
            # redirect stdout to connection
            sys.stdout.flush()
            stdout = sys.stdout
            sys.stdout = connfile
            execfunc(parse_command(command))
            #connfile.write(KEEPNOTE_EOF)
            connfile.flush()
        except:
            keepnote.log_error()
            pass
        finally:
            sys.stdout = stdout

        # close connection
        connfile.close()
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()

    except socket.error, e:
        # socket error, close connection
        print >>sys.stderr, e, ": error with connection"
        conn.close()


#=============================================================================
# commands read/write


def unescape(text):
    """Unescape a string from the socket"""
    text2 = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            if text[i+1] == "n":
                # newline
                text2.append("\n")
            else:
                # literal
                text2.append(text[i+1])
            i += 1
        else:
            text2.append(text[i])

        i += 1

    return "".join(text2)


def escape(text):
    """Escape a string for sending over the socket"""
    text2 = []
    for c in text:
        if c == "\n":
            text2.append("\\n")
        elif c == " ":
            text2.append("\\ ")
        elif c == "\\":
            text2.append("\\\\")
        else:
            text2.append(c)

    return "".join(text2)


def split_args(text):
    args = []
    last = 0
    for i in xrange(len(text)):
        if text[i] == " " and (i == 0 or text[i-1] != "\\"):
            args.append(text[last:i])
            last = i + 1
    args.append(text[last:])
    return args


def parse_command(text):
    """Parse a command from the socket"""
    return [unescape(x) for x in split_args(text)]


def format_command(argv):
    """Format a command from the socket"""
    return " ".join(escape(x) for x in argv)


class CommandExecutor (object):

    def __init__(self):
        self._execfunc = None
        self._app = None
        self._port = None

    def set_app(self, app):
        """Set the app for the CommandExecutor"""
        self._app = app

    def set_port(self, port):
        """Set the socket port for the CommandExecutor"""
        self._port = port

    def _listen(self, fd, execfunc):
        """Listen for other processes to send commands"""

        # open socket and record port number in lock file
        passwd = make_passwd()
        sock, port = open_socket(self._port)
        if port is None:
            raise Exception("Could not open socket")
        write_lock_file(fd, port, passwd)

        self._execfunc = execfunc

        # start listening to socket for remote commands
        thread.start_new_thread(listen_commands,
                                (sock, process_connection, (passwd,
                                                            self.execute)))

    def _connect(self, fd):
        """Connect to the main process"""

        port, passwd = read_lock_file(fd)
        os.close(fd)
        fd = None

        # use port number to connect
        s = socket.socket(socket.AF_INET)
        s.connect(("localhost", port))

        # ensure header matches
        s.settimeout(5.0)  # wait up to 5 seconds to connect
        header = s.recv(len(KEEPNOTE_HEADER))
        assert header == KEEPNOTE_HEADER

        # send password
        connfile = s.makefile()
        connfile.write("%s\n" % passwd)
        connfile.flush()

        def execute(app, argv):
            # send command
            connfile.write(format_command(argv) + "\n")
            connfile.flush()

            # display return
            try:
                while 1:
                    c = s.recv(1024*4)
                    if len(c) == 0:
                        break
                    sys.stdout.write(c)
            except socket.error:
                pass
            sys.stdout.flush()

            # close socket
            connfile.close()
            s.close()
        self._execfunc = execute

    def setup(self, execfunc):
        """
        Returns True if this is the main process, False otherwise
        execfunc  -- a function to call with arguments if this is the
                     main process
        """

        tries = 2
        lock_file = keepnote.get_user_lock_file()

        for i in range(tries):
            acquire, fd = get_lock_file(lock_file)

            if acquire:
                # we are main process, listen for others
                self._listen(fd, execfunc)
                return True

            else:
                # we are slave process.
                # connect to main process through socket
                try:
                    self._connect(fd)
                    return False

                except Exception:
                    # lockfile does not contain proper port number
                    # remove lock file and attempt to acquire again
                    try:
                        if fd:
                            os.close(fd)
                    except Exception:
                        # ignore failure to close fd
                        pass

                    # may raise exception
                    os.remove(lock_file)

        raise Exception("cannot get lock")

    def execute(self, argv):
        """Send a command to the main thread"""
        self._execfunc(self._app, argv)


def get_command_executor(func, port=None):
    """Make a CommandExecutor object that wraps the given function"""

    try:
        cmd_exec = CommandExecutor()
        cmd_exec.set_port(port)
        main_proc = cmd_exec.setup(func)
    except:
        # backup if error is encountered acquiring lock
        main_proc = True
        cmd_exec = CommandExecutor()

    return main_proc, cmd_exec


#=============================================================================
# old code

'''
# TODO: maybe not needed
class QuotedOutput (object):
    def __init__(self, out):
        self.__out = out
        self.mode = out.mode

    def write(self, text):
        for c in format_result(text):
            self.__out.write(c)

    def closed(self):
        return self.__out.closed()

    def flush(self):
        self.__out.flush()

# TODO: maybe not needed
def format_result(result):

    for c in result:
        if c == KEEPNOTE_EOF or c == KEEPNOTE_ESCAPE:
            yield KEEPNOTE_ESCAPE
        yield c

# TODO: maybe not needed
def parse_result(result):
    """
    Parse result text

    The end of the socket stream is determined by this syntax

    Let $ be \x00
    Let \ be \xff

    abc$          =>  abc
    abc\$def$     =>  abc$def
    abc\\$        =>  abc\
    abcd\\\$def$  =>  abc\$def

    """

    escape = False

    for c in result:
        if not escape and c == KEEPNOTE_ESCAPE:
            # begin escape mode, next char
            escape = True
            continue
        else:
            # end escape mode
            escape = False

        if not escape and c == KEEPNOTE_EOF:
            # end of file
            break

        # output char
        yield c

'''


'''
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
'''
