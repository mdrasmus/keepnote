
import os

from keepnote import notebook as notebooklib
from keepnote import safefile


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
        # can't read notebook
        # TODO: add code to handle this situation
        # e.g. try old notebook version load()
        raise


    # NOTE: for now, this code only works for version 1 to 2

    assert desired_version == 2

    if notebook.pref.version == 1:
        from keepnote.compat import notebook_v1 as old_notebooklib

        # try to load old notebook (may raise exceptions)
        notebook = old_notebooklib.NoteBook()
        notebook.load(filename)

        # write new notebook preference file
        notebook.pref.version = 2
        notebook.write_preferences()

        # recursively upgrade notes
        def walk(node):            
            
            try:
                if isinstance(node, old_notebooklib.NoteBookTrash):
                    # create new content-type: trash
                    node.set_attr("content_type", notebooklib.CONTENT_TYPE_TRASH)

                elif isinstance(node, old_notebooklib.NoteBookPage):
                    # remove old "page.xml" meta file
                    os.remove(node.get_meta_file())
                    node.set_attr("content_type", notebooklib.CONTENT_TYPE_PAGE)

                elif isinstance(node, old_notebooklib.NoteBookDir):
                    # create new content-type: dir
                    node.set_attr("content_type", notebooklib.CONTENT_TYPE_DIR)

                else:
                    raise Exception("unknown node: '%s'" % str(type(node)))

                # remove old kind attribute
                del node._attr["kind"]
                
                # write to "node.xml" meta file
                write_meta_data(node)
                
                    
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
    


def write_meta_data(node):
    
    try:
        filename = notebooklib.get_node_meta_file(node.get_path())
        out = safefile.open(filename, "w")
        out.write(notebooklib.XML_HEADER)
        out.write("<node>\n"
                  "<version>2</version>\n")

        for key, val in node._attr.iteritems():
            attr = node._notebook.notebook_attrs.get(key, None)

            if attr is not None:
                out.write('<attr key="%s">%s</attr>\n' %
                          (key, attr.write(val)))
                
            elif key == "content_type":
                out.write('<attr key="content_type">%s</attr>\n' % val)

        out.write("</node>\n")
        out.close()
    except Exception, e:
        raise notebooklib.NoteBookError("Cannot write meta data", e)

