"""

    Helper functions for windows

"""

import os


def get_local_drives():
    # hack that doesn't require win32api
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        if os.path.exists(drive + ":\\"):
            yield drive + ":\\"


def find_path(path, drives=None):
    """Find a path that exists on a list of drives"""
	
    if drives is None:
        drives = get_local_drives()
	
    for drive in drives:
        path2 = os.path.join(drive, path)
        if os.path.exists(path2):
            return path2
    
    raise Exception("Path '%s' not found" % path)
