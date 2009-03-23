
import os
from xml.sax.saxutils import escape


from keepnote import notebook as notebooklib
from keepnote import safefile
from keepnote.compat import notebook_update_v1_2


def update_notebook(filename, desired_version, warn=lambda w: False,
                    verify=True):
    """Updates a notebook to the desired version (downgrading not implemented)"""

    # try to open notebook (may raise exceptions)
    try:
        notebook = notebooklib.NoteBook()
        notebook.load(filename)

        if notebook.pref.version >= desired_version:
            return
    except:
        # try old notebook version load()
        notebook_update_v1_2.update_notebook(filename, 2, warn=warn,
                                             verify=verify)
            
    # NOTE: only works for version 2 --> 3

    assert desired_version == 3

    if notebook.pref.version == 2:
        from keepnote.compat import notebook_v2 as old_notebooklib

        # try to load old notebook (may raise exceptions)
        notebook = old_notebooklib.NoteBook()
        notebook.load(filename)

        # write new notebook preference file
        notebook.pref.version = 3
        notebook.write_preferences()

        # recursively upgrade notes
        def walk(node):                        
            try:
                node._version = 3
                node.write_meta_data()
            except Exception, e:
                if not warn(e):
                    raise notebooklib.NoteBookError("Could not update notebook", e)

            # recurse
            for child in node.get_children():
                walk(child)
        walk(notebook)

    # verify notebook updated successfully
    if verify:
        notebook = notebooklib.NoteBook()
        notebook.load(filename)

        def walk(node):
            for child in node.get_children():
                walk(child)
        walk(notebook)
