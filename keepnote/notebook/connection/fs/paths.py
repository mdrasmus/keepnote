import os


# Constants.
NODE_META_FILE = u"node.xml"


def get_node_meta_file(nodepath):
    """Return the metadata file for a node."""
    return os.path.join(nodepath, NODE_META_FILE)


def path_local2node(filename):
    """
    Converts a local path to a node path

    On unix:

      aaa/bbb/ccc  =>  aaa/bbb/ccc

    On windows:

      aaa\bbb\ccc  =>  aaa/bbb/ccc
    """

    if os.path.sep == u"/":
        return filename
    return filename.replace(os.path.sep, u"/")


def path_node2local(filename):
    """
    Converts a node path to a local path

    On unix:

      aaa/bbb/ccc  =>  aaa/bbb/ccc

    On windows:

      aaa/bbb/ccc  =>  aaa\bbb\ccc
    """

    if os.path.sep == u"/":
        return filename
    return filename.replace(u"/", os.path.sep)
