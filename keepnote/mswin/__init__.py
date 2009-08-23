
try:
    from win32com.shell import shell
except:
    pass


def get_my_documents():
    """Return the My Docuemnts folder"""
    
    df = shell.SHGetDesktopFolder()
    pidl = df.ParseDisplayName(0, None,  
        "::{450d8fba-ad25-11d0-98a8-0800361b1103}")[1]
    mydocs = shell.SHGetPathFromIDList(pidl)

    return mydocs


