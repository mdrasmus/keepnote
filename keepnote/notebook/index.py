"""

    KeepNote
    Notebook indexing

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

#from sqlite3 import dbapi2 as sqlite

import keepnote



INDEX_FILE = "index.sqlite"



def get_index_file(notebook):
    return os.path.join(notebook.get_pref_dir(), INDEX_FILE)



class NoteBookIndex (object):
    """Index for a NoteBook"""

    def __init__(self, notebook):
        self._notebook = notebook

        #self.init_index()


    def init_index(self):
        
        index_file = get_index_file(self._notebook)
        if not os.path.exists(index_file):
            # create index
            con = sqlite.connect(index_file) #, isolation_level="DEFERRED")
            cur = con.cursor()

            # init NodeGraph table
            query = """CREATE TABLE IF NOT EXISTS NodeGraph 
                       (nodeid TEXT,
                        parentid TEXT,
                        basename TEXT,
                        symlink BOOLEAN);
                    """
            cur.execute(query)
            con.commit()

            
            con.close()


    
