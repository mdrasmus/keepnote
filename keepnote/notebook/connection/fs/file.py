import os
import shutil

from keepnote import safefile
from keepnote.notebook.connection import FileError
from keepnote.notebook.connection import path_join
from keepnote.notebook.connection import UnknownFile
from keepnote.notebook.connection.fs.paths import get_node_meta_file
from keepnote.notebook.connection.fs.paths import path_node2local
from keepnote.notebook.connection.fs.paths import NODE_META_FILE


def get_node_filename(node_path, filename):
    """
    Returns a full local path to a node file

    node_path  -- local path to a node
    filename   -- node path to attached file
    """

    if filename.startswith("/"):
        filename = filename[1:]

    return os.path.join(node_path, path_node2local(filename))


class FileFS(object):
    """
    Implements the NoteBook File API using the file-system.
    """

    def __init__(self, nodeid2path):
        """
        nodeid2path: a function that returns a filesystem path for a nodeid.
        """
        self._nodeid2path = nodeid2path

    def get_node_path(self, nodeid):
        return self._nodeid2path(nodeid)

    def open_file(self, nodeid, filename, mode="r", codec=None, _path=None):
        """Open a node file"""
        if mode not in "rwa":
            raise FileError("mode must be 'r', 'w', or 'a'")

        if filename.endswith("/"):
            raise FileError("filename '%s' cannot end with '/'" % filename)

        path = self.get_node_path(nodeid) if _path is None else _path
        fullname = get_node_filename(path, filename)
        dirpath = os.path.dirname(fullname)

        try:
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)

            # NOTE: always use binary mode to ensure no
            # Window-specific line ending conversion
            stream = safefile.open(fullname, mode + "b", codec=codec)
        except Exception, e:
            raise FileError(
                "cannot open file '%s' '%s': %s" %
                (nodeid, filename, str(e)), e)

        return stream

    def delete_file(self, nodeid, filename, _path=None):
        """Delete a node file"""
        path = self.get_node_path(nodeid) if _path is None else _path
        filepath = get_node_filename(path, filename)

        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
            elif filename.endswith('/') and os.path.isdir(filepath):
                shutil.rmtree(filepath)
            else:
                # filename may not exist, delete is successful by default
                pass
        except Exception, e:
            raise FileError("error deleting file '%s' '%s'" %
                            (nodeid, filename), e)

    def create_dir(self, nodeid, filename, _path=None):
        """Create directory within node."""
        if not filename.endswith("/"):
            raise FileError("filename '%s' does not end with '/'" % filename)

        path = self.get_node_path(nodeid) if _path is None else _path
        fullname = get_node_filename(path, filename)

        try:
            if not os.path.isdir(fullname):
                os.makedirs(fullname)
        except Exception, e:
            raise FileError(
                "cannot create dir '%s' '%s'" % (nodeid, filename), e)

    def list_dir(self, nodeid, filename="/", _path=None):
        """List data files in node."""
        if not filename.endswith("/"):
            raise FileError("filename '%s' does not end with '/'" % filename)

        path = self.get_node_path(nodeid) if _path is None else _path
        path = get_node_filename(path, filename)

        try:
            filenames = os.listdir(path)
        except:
            raise UnknownFile("cannot file file '%s' '%s'" %
                              (nodeid, filename))

        for name in filenames:
            # TODO: extract this as a documented method.
            if (name != NODE_META_FILE and
                    not name.startswith("__")):
                fullname = os.path.join(path, name)
                node_fullname = path_join(filename, name)
                if not os.path.exists(get_node_meta_file(fullname)):
                    # ensure directory is not a node
                    if os.path.isdir(fullname):
                        yield node_fullname + "/"
                    else:
                        yield node_fullname

    def has_file(self, nodeid, filename, _path=None):
        """Return True if file exists."""
        path = self.get_node_path(nodeid) if _path is None else _path
        if filename.endswith("/"):
            return os.path.isdir(get_node_filename(path, filename))
        else:
            return os.path.isfile(get_node_filename(path, filename))

    def move_file(self, nodeid1, filename1, nodeid2, filename2,
                  _path1=None, _path2=None):
        """Rename a node file."""
        path1 = self.get_node_path(nodeid1) if _path1 is None else _path1
        path2 = self.get_node_path(nodeid2) if _path2 is None else _path2
        filepath1 = get_node_filename(path1, filename1)
        filepath2 = get_node_filename(path2, filename2)
        try:
            # remove files in the way
            if os.path.isfile(filepath2):
                os.remove(filepath2)
            if os.path.isdir(filename2):
                shutil.rmtree(filepath2)

            # rename file
            os.rename(filepath1, filepath2)
        except Exception, e:
            raise FileError("could not move file '%s' '%s'" %
                            (nodeid1, filename1), e)

    def copy_file(self, nodeid1, filename1, nodeid2, filename2,
                  _path1=None, _path2=None):
        """
        Copy a file between two nodes.

        If nodeid is None, filename is assumed to be a local file.
        """
        # Determine full filenames.
        if nodeid1 is None:
            fullname1 = filename1
        else:
            path1 = self.get_node_path(nodeid1) if not _path1 else _path1
            fullname1 = get_node_filename(path1, filename1)

        if nodeid2 is None:
            fullname2 = filename2
        else:
            path2 = self.get_node_path(nodeid2) if not _path2 else _path2
            fullname2 = get_node_filename(path2, filename2)

        try:
            if os.path.isfile(fullname1):
                shutil.copy(fullname1, fullname2)
            elif os.path.isdir(fullname1):
                # TODO: handle case where filename1 = "/" and
                # filename2 could be an existing directory
                shutil.copytree(fullname1, fullname2)
        except Exception, e:
            raise FileError(
                "unable to copy file '%s' '%s'" % (nodeid1, filename1), e)
