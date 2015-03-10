
# keepnote imports
from keepnote.notebook.connection import mem

from .test_notebook_conn import TestConnBase


class Mem (TestConnBase):

    def test_api(self):
        # initialize a notebook
        conn = mem.NoteBookConnectionMem()
        self._test_api(conn)

    def test_notebook(self):
        # initialize a notebook

        conn = mem.NoteBookConnectionMem()
        self._test_notebook(conn, 'n1')
