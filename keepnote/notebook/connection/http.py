"""

    KeepNote

    Serving/accessing KeepNote notebooks over HTTP

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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

# python imports
from collections import defaultdict
import contextlib
import httplib
import json
import urllib
import urlparse

# keepnote imports
from keepnote import plist
import keepnote.notebook.connection as connlib
from keepnote.notebook.connection import NoteBookConnection


XML_HEADER = u"""\
<?xml version="1.0" encoding="UTF-8"?>
"""


#=============================================================================
# Node URL scheme

def determine_path_prefix(path, prefixes=()):
    """
    Prefixes must end with a slash
    """

    for prefix in prefixes:
        if path.startswith(prefix):
            return prefix

    return ""


def parse_node_path(path, prefixes=("/")):

    # skip over prefix
    prefix = determine_path_prefix(path, prefixes)
    path = path[len(prefix):]

    # find end of nodeid (ends with an optional slash)
    i = path.find("/")
    if i != -1:
        nodeid = path[:i]
        filename = urllib.unquote(path[i+1:])
        if filename == "":
            filename = "/"
    else:
        nodeid = path
        filename = None

    return urllib.unquote(nodeid), filename


def format_node_path(prefix, nodeid="", filename=None):
    """
    prefix must end with "/"
    """
    nodeid = nodeid.replace("/", "%2F")
    if filename is not None:
        return urllib.quote("%s%s/%s" % (prefix, nodeid, filename))
    else:
        return urllib.quote(prefix + nodeid)


def format_node_url(host, prefix, nodeid, filename=None, port=80):
    portstr = ":" + str(port) if port != 80 else ""
    return "http://%s%s/%s" % (host, portstr,
                               format_node_path(prefix, nodeid, filename))


#=============================================================================
# NoteBook HTTP client

class NoteBookConnectionHttp (NoteBookConnection):

    def __init__(self, version=2):
        self._netloc = ""
        self._prefix = "/"
        self._conn = None
        self._title_cache = NodeTitleCache()
        self._version = version

    def connect(self, url):
        parts = urlparse.urlsplit(url)

        self._netloc = parts.netloc
        self._prefix = parts.path + 'nodes/'
        self._notebook_prefix = parts.path
        self._conn = httplib.HTTPConnection(self._netloc)
        self._title_cache.clear()
        #self._conn.set_debuglevel(1)

    def close(self):
        self._conn.close()

    def save(self):
        # POST http://host/prefix/?save

        self._request(
            'POST', format_node_path(self._notebook_prefix) + "?save")
        self._conn.getresponse()
        pass

    def _request(self, action, url, body=None, headers={}):
        try:
            return self._conn.request(action, url, body, headers)
        except httplib.ImproperConnectionState:
            # restart connection
            self._conn = httplib.HTTPConnection(self._netloc)
            return self._request(action, url, body, headers)

    def load_data(self, stream):
        if self._version == 2:
            return json.loads(stream.read())
        else:
            return plist.load(stream)

    def loads_data(self, data):
        if self._version == 2:
            return json.loads(data)
        else:
            return plist.loads(data)

    def dumps_data(self, data):
        if self._version == 2:
            return json.dumps(data)
        else:
            return plist.dumps(data)

    #===========================================

    def create_node(self, nodeid, attr):

        body_content = self.dumps_data(attr).encode("utf8")
        self._request('POST', format_node_path(self._prefix, nodeid),
                      body_content)
        result = self._conn.getresponse()
        if result.status == httplib.FORBIDDEN:
            raise connlib.NodeExists()
        elif result.status != httplib.OK:
            raise connlib.ConnectionError("unexpected error")

        self._title_cache.update_attr(attr)

    def read_node(self, nodeid):

        self._request('GET', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()
        if result.status == httplib.OK:
            try:
                attr = self.load_data(result)
                self._title_cache.update_attr(attr)
                return attr
            except Exception, e:
                raise connlib.ConnectionError(
                    "unexpected error '%s'" % str(e), e)
        else:
            raise connlib.UnknownNode(nodeid)

    def update_node(self, nodeid, attr):

        body_content = self.dumps_data(attr).encode("utf8")
        self._request('PUT', format_node_path(self._prefix, nodeid),
                      body_content)
        result = self._conn.getresponse()
        if result.status == httplib.NOT_FOUND:
            raise connlib.UnknownNode()
        elif result.status != httplib.OK:
            raise connlib.ConnectionError()
        self._title_cache.update_attr(attr)

    def delete_node(self, nodeid):

        self._request('DELETE', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()
        if result.status == httplib.NOT_FOUND:
            raise connlib.UnknownNode()
        elif result.status != httplib.OK:
            raise connlib.ConnectionError()
        self._title_cache.remove(nodeid)

    def has_node(self, nodeid):
        """Returns True if node exists"""

        # HEAD nodeid/filename
        self._request('HEAD', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()
        return result.status == httplib.OK

    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        # GET /
        self._request('GET', format_node_path(self._prefix))
        result = self._conn.getresponse()

        if result.status == httplib.NOT_FOUND:
            raise connlib.UnknownNode()
        if result.status != httplib.OK:
            raise connlib.ConnectionError()

        # Currently only the first rootid is returned.
        data = self.load_data(result)
        rootid = data['rootids'][0]
        return rootid

    #===============
    # file API

    def open_file(self, nodeid, filename, mode="r", codec=None):
        """Open a file contained within a node"""

        # read: GET nodeid/file
        # write: POST nodeid/file
        # append: POST nodeid/file?mode=a

        class HttpFile (object):
            def __init__(self, codec=None):
                self.data = []
                self.codec = codec

            def write(self, data):
                if codec:
                    data = data.encode(codec)
                self.data.append(data)

            def close(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, type, value, tb):
                self.close()

        # Cannot open directories.
        if filename.endswith("/"):
            raise connlib.FileError()

        if mode == "r":
            self._request(
                'GET', format_node_path(self._prefix, nodeid, filename))
            result = self._conn.getresponse()
            if result.status == httplib.OK:
                stream = contextlib.closing(result)
                stream.read = result.read
                stream.close = result.close
                return stream
            else:
                raise connlib.FileError()

        elif mode == "w":
            stream = HttpFile(codec)

            def on_close():
                body_content = "".join(stream.data)
                self._request(
                    'POST', format_node_path(self._prefix, nodeid, filename),
                    body_content)
                self._conn.getresponse()
            stream.close = on_close
            return stream

        elif mode == "a":
            stream = HttpFile(codec)

            def on_close():
                body_content = "".join(stream.data)
                self._request(
                    'POST', format_node_path(self._prefix, nodeid, filename) +
                    "?mode=a", body_content)
                self._conn.getresponse()
            stream.close = on_close
            return stream

        else:
            raise connlib.FileError("unknown mode '%s'" % mode)

    def delete_file(self, nodeid, filename):
        """Open a file contained within a node"""

        # DELETE nodeid/file
        self._request(
            'DELETE', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        if result.status != httplib.OK:
            raise connlib.FileError()

    def create_dir(self, nodeid, filename):

        # Directories must end with "/"
        if not filename.endswith("/"):
            raise connlib.FileError()

        # PUT nodeid/dir/
        self._request(
            'PUT', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        if result.status != httplib.OK:
            raise connlib.FileError()

    def list_dir(self, nodeid, filename="/"):
        """
        List data files in node
        """
        # Cannot list files.
        if not filename.endswith("/"):
            raise connlib.FileError()

        # GET nodeid/dir/
        self._request(
            'GET', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        if result.status == httplib.OK:
            try:
                if self._version == 1:
                    return self.load_data(result)
                else:
                    data = self.load_data(result)
                    return data['files']
            except Exception, e:
                raise connlib.ConnectionError(
                    "unexpected response '%s'" % str(e), e)
        else:
            raise connlib.FileError("cannot list node")

    def has_file(self, nodeid, filename):

        # HEAD nodeid/filename
        self._request(
            'HEAD', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        return result.status == httplib.OK

    #---------------------------------
    # indexing/querying

    def index_raw(self, query):
        # POST /?index
        # query plist encoded
        body_content = self.dumps_data(query).encode("utf8")
        self._request(
            'POST', format_node_path(self._notebook_prefix) + "?index",
            body_content)
        result = self._conn.getresponse()
        if result.status == httplib.OK:
            try:
                return self.load_data(result)
            except Exception, e:
                raise connlib.ConnectionError(
                    "unexpected response '%s'" % str(e), e)

    def index(self, query):

        if len(query) > 2 and query[:2] == ["search", "title"]:
            if not self._title_cache.is_complete():
                result = self.index_raw(["search", "title", "%"])
                for nodeid, title in result:
                    self._title_cache.add(nodeid, title)
                self._title_cache.set_complete()

            return list(self._title_cache.get(query[2]))

        elif len(query) == 3 and query[0] == "get_attr" and query[2] == "icon":
            # HACK: fetching icons is too slow right now
            return None

        else:
            return self.index_raw(query)

    def get_node_path(self, nodeid):
        return format_node_url(self._netloc, self._prefix, nodeid)

    def get_file(self, nodeid, filename):
        return format_node_url(self._netloc, self._prefix, nodeid, filename)


class NodeTitleCache (object):
    def __init__(self):
        self._titles = defaultdict(lambda: set())
        self._nodeids = {}
        self._complete = False

    def is_complete(self):
        return self._complete

    def set_complete(self, val=True):
        self._complete = val

    def update_attr(self, attr):
        nodeid = attr.get("nodeid", None)
        title = attr.get("title", None)

        # do nothing if nodeid is not present
        if nodeid is None:
            return

        # if nodeid is in cache, remove it
        self.remove(nodeid)

        # if title is not present, do not cache anything
        if title is None:
            return

        self.add(nodeid, title)

    def remove_attr(self, attr):
        nodeid = attr.get("nodeid", None)

        # do nothing if nodeid is not present
        if nodeid is None:
            return

        self.remove(nodeid)

    def add(self, nodeid, title):
        self._titles[title.lower()].add(nodeid)
        self._nodeids[nodeid] = title

    def remove(self, nodeid):
        # if nodeid is in cache, remove it
        if nodeid in self._nodeids:
            try:
                old_title = self._nodeids[nodeid]
                self._titles[old_title.lower()].remove(nodeid)
                del self._nodeids[nodeid]
            except:
                pass

    def get(self, query):
        query = query.lower()
        for title in self._titles.iterkeys():
            if query in title:
                for nodeid in self._titles[title]:
                    yield (nodeid, self._nodeids[nodeid])

    def clear(self):
        self._titles.clear()
        self._nodeids.clear()
        self._complete = False
