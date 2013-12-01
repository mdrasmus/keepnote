"""

    KeepNote
    Notebook updating

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
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

import os

from keepnote import notebook as notebooklib
from keepnote.compat import notebook_update_v1_2, notebook_update_v5_6


def update_notebook(filename,
                    desired_version=notebooklib.NOTEBOOK_FORMAT_VERSION,
                    warn=lambda w: False,
                    verify=True):
    """
    Updates a notebook to the desired version (downgrading not implemented)
    """

    # try to open notebook (may raise exceptions)
    version = notebooklib.get_notebook_version(filename)
    if version >= desired_version:
        return

    while version < desired_version:

        # upgrade 1 --> 2
        if version == 1:
            notebook_update_v1_2.update_notebook(filename, 2, warn=warn,
                                                 verify=verify)
            version = 2

        # upgrade 2 --> 3
        elif version == 2:
            from keepnote.compat import notebook_v2
            from keepnote.compat import notebook_v3

            # try to load old notebook (may raise exceptions)
            notebook = notebook_v2.NoteBook()
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
                        raise notebooklib.NoteBookError(
                            "Could not update notebook", e)

                # recurse
                for child in node.get_children():
                    walk(child)
            walk(notebook)

            version = notebook.pref.version

            # verify notebook updated successfully by walking all nodes.
            if verify:
                notebook = notebook_v3.NoteBook()
                notebook.load(filename)

                def walk(node):
                    for child in node.get_children():
                        walk(child)
                walk(notebook)
                notebook.close()

        # upgrade 3 --> 4
        elif version == 3:
            from keepnote.compat import notebook_v3

            # try to load old notebook (may raise exceptions)
            notebook = notebook_v3.NoteBook()
            notebook.load(filename)
            notebook.pref.version = 4

            # Clear out old index.
            index_file = os.path.join(notebook.get_pref_dir(), "index.sqlite")
            if os.path.exists(index_file):
                os.remove(index_file)

            # Write new preferences.
            notebook_v3.write_new_preferences(notebook.pref,
                                              notebook.get_pref_file())
            notebook.close()
            version = 4

        # upgrade 4 --> 5
        elif version == 4:
            from keepnote.compat import notebook_v4

            # try to load old notebook (may raise exceptions)
            notebook = notebook_v4.NoteBook()
            notebook.load(filename)
            notebook.pref.set("version", 5)
            notebook.save(force=True)

            #if notebook.index_needed():
            #    notebook.clear_index()

            notebook.close()
            version = 5

        elif version == 5:
            notebook_update_v5_6.update(filename)
            version = 6
