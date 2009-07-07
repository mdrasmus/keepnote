"""
   
    KeepNote
    Notebook updating

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
        # NOTE: preference is completely backwards compat so far
        # So there is nothing left to try
        raise


    # NOTE: only works for version 1,2 --> 3

    assert desired_version == 3

    # upgrade 1 --> 2
    if notebook.pref.version == 1:
        notebook_update_v1_2.update_notebook(filename, 2, warn=warn,
                                             verify=verify) 
        notebook = notebooklib.NoteBook()
        notebook.load(filename)
        

    # upgrade 2 --> 3
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
