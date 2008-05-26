"""

    Helper functions for windows

"""


import win32api


def get_local_drives():
    """Get a list of all local drives"""
    return [ drive for drive in
             win32api.GetLogicalDriveStrings().split('\x00')[:-1]
             if win32file.GetDriveType(drive) in (win32file.DRIVE_FIXED,
                                                  win32file.DRIVE_CDROM,
                                                  win32file.DRIVE_REMOVABLE)]

def find_path(path, drives=get_local_drives()):
    """Find a path that exists on a list of drives"""
    for drive in drives:
        path2 = os.path.join(drive, path)
        if os.path.exists(path2):
            return path2
    return None
