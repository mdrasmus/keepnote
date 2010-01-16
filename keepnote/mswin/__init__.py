

import sys

# make sure py2exe finds win32com
try:
    import modulefinder
    import win32com
    for p in win32com.__path__[1:]:
        modulefinder.AddPackagePath("win32com", p)
    for extra in ["win32com.shell"]:
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)
except ImportError:
    # no build path setup, no worries.
    pass


try:
    from win32com.shell import shell
    import win32api
    import win32gui
    import win32con
    import win32ui

    import ctypes.windll.kernel32

except:
    pass


def get_my_documents():
    """Return the My Docuemnts folder"""
    
    df = shell.SHGetDesktopFolder()
    pidl = df.ParseDisplayName(0, None,  
        "::{450d8fba-ad25-11d0-98a8-0800361b1103}")[1]
    mydocs = shell.SHGetPathFromIDList(pidl)

    return mydocs


def set_env(key, val):
    ctypes.windll.kernel32.SetEnvironmentVariableW(key, val)

