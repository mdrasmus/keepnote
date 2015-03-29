(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
var keepnote = require('./keepnote.jsx');

window.KeepNoteApp = keepnote.KeepNoteApp;


},{"./keepnote.jsx":2}],2:[function(require,module,exports){
// Import libs.
if (typeof require !== 'undefined') {
    var notebooklib = require('./notebook.js');
    var NoteBook = notebooklib.NoteBook;

    var treeview = require('./treeview.jsx');
    var NotebookTree = treeview.NotebookTree;
}


// Parse a page's HTML into DOM elements.
function parsePageHtml(node, html) {
    // Parse page html.
    var parser = new DOMParser();
    var htmlDoc = parser.parseFromString(html, 'text/html');
    var body = $(htmlDoc.getElementsByTagName('body'));

    convertHtmlForDisplay(node, body);
    return body;
}


function formatPageHtml(node, body) {
    var htmlHeader = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n' +
        '<html xmlns="http://www.w3.org/1999/xhtml"><body>');
    var htmlFooter = '</body></html>';

    convertHtmlForStorage(node, body);

    // Serialize to XHTML.
    var serializer = new XMLSerializer();
    var xhtml = [];
    body.contents().each(function (i) {
        xhtml.push(serializer.serializeToString($(this).get(0)));
    });
    xhtml = xhtml.join('');

    // Add header and footer.
    return htmlHeader + xhtml + htmlFooter;
}


function isAbsoluteUrl(url) {
    return url.match(/^(?:[a-zA-Z]+:)?\/\//);
}


function convertHtmlForDisplay(node, body) {
    var baseUrl = node.url() + '/';

    // Adjust all relative image urls for display.
    body.find('img').each(function (i) {
        var img = $(this);
        var src = img.attr('src');

        if (!isAbsoluteUrl(src))
            img.attr('src', baseUrl + src);
    });
}


function convertHtmlForStorage(node, body) {
    var baseUrl = node.url() + '/';

    // Adjust all img urls for storage.
    body.find('img').each(function (i) {
        var img = $(this);
        var src = img.attr('src');

        // TODO: prevent image loading.
        // Strip baseUrl if present.
        if (src.substr(0, baseUrl.length) === baseUrl)
            img.attr('src', src.substr(baseUrl.length));

        // Remove unneeded title attribute.
        img.removeAttr('title');
    });
}


var PageToolbar = React.createClass({displayName: "PageToolbar",
    render: function () {
        return (React.createElement("div", {className: "page-toolbar", id: "page-toolbar"}, 
          React.createElement("a", {href: "javascript:;", onClick: this.props.onShowAttr}, "attr")
        ));
    }
});


var PageEditor = React.createClass({displayName: "PageEditor",
    render: function () {
        var size = this.props.size;
        var toolbarHeight = 25;
        var toolbarSize = [size[0], toolbarHeight];
        var editorSize = [size[0], size[1] - toolbarHeight];

        return (React.createElement("div", null, 
          React.createElement(PageToolbar, {ref: "toolbar", 
           style: {width: toolbarSize[0], height: toolbarSize[1]}, 
           onShowAttr: this.props.onShowAttr}), 
          React.createElement("div", {id: "page-editor", ref: "pageEditor", 
           style: {width: editorSize[0], height: editorSize[1]}})
        ));
    },

    componentDidMount: function () {
        var pageEditor = this.refs.pageEditor.getDOMNode();

        // Add editor buttons.
        var toolbar = this.refs.toolbar.getDOMNode();
        var toolbarContent = $($('#page-toolbar-template').html()).children();
        $(toolbar).append(toolbarContent);

        // Setup editor.
        this.editor = new wysihtml5.Editor('page-editor', {
            toolbar: 'page-toolbar',
            parserRules: wysihtml5ParserRules
        });

        // Attach listener to link double clicks.
        var that = this;
        $(pageEditor).on('dblclick', 'a', function (event) {
            event.preventDefault();
            if (that.props.onVisitLink)
                that.props.onVisitLink($(this).attr('href'));
        });

        this.linkDialog = $('[data-wysihtml5-dialog=createLink]');
        this.updateLinkDialog();
    },

    componentDidUpdate: function (prevProps, prevState) {
        this.updateLinkDialog();
    },

    updateLinkDialog: function () {
        var size = this.props.size;
        var pageEditor = this.refs.pageEditor.getDOMNode();

        // TODO: move this into render.
        // Align dialog to bottom of editor.
        var toolbarHeight = 25;
        var rect = pageEditor.getBoundingClientRect();

        this.linkDialog.css({
            position: 'absolute',
            width: size[0],
            height: toolbarHeight,
            top: rect.bottom - toolbarHeight
        });
    },

    clear: function () {
        var editor = $(this.refs.pageEditor.getDOMNode());
        editor.empty();
    },

    // Set content for page editor.
    setContent: function (content) {
        var editor = $(this.refs.pageEditor.getDOMNode());
        editor.empty();
        editor.append(content);
    },

    // Get content from page editor.
    getContent: function () {
        var editor = $(this.refs.pageEditor.getDOMNode());
        var body = editor.clone();
        return body;
    }
});


var SearchBox = React.createClass({displayName: "SearchBox",
    render: function () {
        return React.createElement("div", {className: "search"}, React.createElement("input", {ref: "search", type: "text"}));
    },

    componentDidMount: function () {
        var input = $(this.refs.search.getDOMNode());

        input.typeahead({
            highlight: true
        },
        {
            name: 'pages',
            source: this.getResults
        }).on('typeahead:selected', this.onSelected);
    },

    focus: function () {
        var input = $(this.refs.search.getDOMNode());
        input.focus().select();
    },

    getResults: function (query, cb) {
        this.props.search(query).done(function (result) {
            var suggestions = [];
            for (var i=0; i<result.length; i++) {
                suggestions.push({
                    value: result[i][1],
                    nodeid: result[i][0]
                });
            }
            cb(suggestions);
        });
    },

    onSelected: function (event, suggestion, dataset) {
        this.props.onViewNodeId(suggestion.nodeid);
    }
});


var KeepNoteView = React.createClass({displayName: "KeepNoteView",
    getInitialState: function () {
        return {
            currentNode: null,
            currentTreeNode: null,
            bindings: new KeyBinding()
        };
    },

    componentDidMount: function () {
        var bindings = this.state.bindings;
        $('body').keypress(bindings.processEvent.bind(bindings));
        this.initKeyBindings();

        // Register back button event.
        window.onpopstate = function (event) {
            this.viewPageByUrl(window.location.pathname, {
                skipHistory: true
            });
        }.bind(this);
    },

    initKeyBindings: function () {
        var bindings = this.state.bindings;
        bindings.add('ctrl s', this.save);
        bindings.add('ctrl k', this.focusSearch);
        bindings.add('ctrl n', this.newNode);
        bindings.add('ctrl shift N', this.newChildNode);
    },

    render: function () {
        var app = this.props.app;
        var root = app.notebook ? app.notebook.root : null;

        var topbarHeight = 30;
        var treeWidth = 300;
        var listviewHeight = 300;

        var windowSize = [$(window).width(), $(window).height()];
        var appSize = [windowSize[0], windowSize[1]];
        var topbarSize = [windowSize[0], topbarHeight];
        var treeSize = [treeWidth - 2, appSize[1] - topbarHeight];

        var pageWidth = windowSize[0] - treeSize[0];
        var rightSize = [pageWidth, appSize[1] - topbarHeight];

        var listviewSize = [pageWidth, listviewHeight];
        var pageSize = [pageWidth, appSize[1] - topbarHeight - listviewHeight];

        var treeview = root ?
            React.createElement(NotebookTree, {
             node: root, 
             currentNode: this.state.currentTreeNode, 
             onViewNode: this.viewTreeNode, 
             onDeleteNode: this.deleteNode, 
             expandAttr: "expanded", 
             size: treeSize}) :
            React.createElement("div", null);

        var listviewColumns = [
            {
                attr: 'title',
                width: 300
            },
            {
                attr: 'created_time',
                width: 200
            },
            {
                attr: 'modified_time',
                width: 200
            }
        ];
        var listview = this.state.currentTreeNode ?
            React.createElement(NotebookTree, {
             node: this.state.currentTreeNode, 
             currentNode: this.state.currentNode, 
             onViewNode: this.viewNode, 
             onDeleteNode: this.deleteNode, 
             expandAttr: "expanded2", 
             columns: listviewColumns, 
             showHeaders: true, 
             size: listviewSize}) :
            React.createElement("div", null);

        return React.createElement("div", {id: "app"}, 
          React.createElement("div", {id: "topbar", 
           style: {width: topbarSize[0], height: topbarSize[1]}}, 
            React.createElement(SearchBox, {ref: "search", 
             search: this.searchTitle, 
             onViewNodeId: this.viewNodeId})
          ), 
          React.createElement("div", {id: "treeview-pane", tabIndex: "1", 
           style: {width: treeSize[0], height: treeSize[1]}}, 
            treeview
          ), 
          React.createElement("div", {id: "page-pane", 
           style: {width: rightSize[0], height: rightSize[1]}}, 
           React.createElement("div", {id: "listview-pane", tabIndex: "1", 
            style: {width: listviewSize[0], height: listviewSize[1]}}, 
            listview
           ), 
            React.createElement(PageEditor, {ref: "pageEditor", 
             size: pageSize, 
             onShowAttr: this.onShowAttr, 
             onVisitLink: this.visitLink})
          )
        );
    },

    save: function () {
        this.savePage();
        this.props.app.notebook.save();
    },

    newNode: function () {
        var notebook = this.props.app.notebook;
        if (!notebook)
            return $.Deferred().resolve();

        var root = notebook.root;
        var node = this.state.currentNode;
        var parent = null;
        var index = null;

        if (!node || node === root) {
            parent = root;
            index = null;
        } else {
            parent = node.parents[0];
            index = (node.get('order') || 0) + 1;
        }

        return notebook.newNode(parent, index).done(function (node) {
            this.viewNode(node);
        }.bind(this));
    },

    newChildNode: function () {
        var notebook = this.props.app.notebook;
        if (!notebook)
            return $.Deferred().resolve();

        var parent = this.state.currentNode;
        if (!parent)
            parent = notebook.root;
        return notebook.newNode(parent).done(function (node) {
            this.viewNode(node);
        }.bind(this));
    },

    deleteNode: function (node) {
        var notebook = this.props.app.notebook;
        return notebook.deleteNode(node);
    },

    viewNode: function (node, options) {
        var options = options || {};
        var skipHistory = options.skipHistory || false;
        var treeNode = options.treeNode || null;

        // Save history.
        if (!skipHistory) {
            var state = {
                currentNodeId: node.id
            };
            var pageUrl = this.getNodePageUrl(node);
            window.history.pushState(state, node.get('title'), pageUrl);
        }

        // Set window title.
        node.ensureFetched().done(function () {
            document.title = node.get('title');
        });

        var setViews = function (treeNode, node) {
            this.setState({
                currentTreeNode: treeNode,
                currentNode: node
            });

            // Ensure listview is expanded make node visible.
            // Ensure all visible nodes in listview are fetched.
            this.expandToNode(node, 'expanded2').then(function () {
                treeNode.fetchExpanded('expanded2');
            });

            // Load node in page editor.
            if (node.isPage()) {
                this.loadPage(node).done(function (content) {
                    this.refs.pageEditor.setContent(content);
                }.bind(this));
            } else {
                // Node is a directory. Display blank page.
                this.refs.pageEditor.clear();
            }
        }.bind(this);

        if (treeNode) {
            setViews(treeNode, node);
        } else {
            this.getVisibleTreeNode(node).done(function (treeNode) {
                setViews(treeNode, node);
            });
        }
    },

    // Expand all nodes leading to node from root. Don't expand node itself.
    expandToNode: function (node, attr) {
        // Walk up parent path.
        function visit(node, expand) {
            return node.ensureFetched().then(function () {
                if (!node.get(attr)) {
                    var attrs = {};
                    attrs[attr] = expand;
                    node.set(attrs);
                    node.save();
                }
                if (node.parents.length > 0)
                    return visit(node.parents[0], true);
            });
        }
        return visit(node, false);
    },

    getVisibleTreeNode: function (node) {
        // Get path to root.
        var rootPath = [];

        // Recursively fetch the root path.
        function visit(node) {
            rootPath.push(node);
            return node.ensureFetched().then(function () {
                if (node.parents.length > 0)
                    return visit(node.parents[0]);
            });
        }

        return visit(node).then(function () {
            // Find first selected or visible node in root path.
            rootPath.reverse();
            var treeNode = null;
            for (var i=0; i<rootPath.length; i++) {
                treeNode = rootPath[i];
                if (!treeNode.get('expanded') ||
                    treeNode === this.state.currentTreeNode)
                    break;
            }
            return treeNode;
        }.bind(this));
    },

    viewTreeNode: function (node, options) {
        options = options || {};
        options.treeNode = node;
        this.viewNode(node, options);
    },

    viewNodeId: function (nodeid, options) {
        var notebook = this.props.app.notebook;
        var node = notebook.getNode(nodeid);
        this.viewNode(node, options);
    },

    viewPageByUrl: function (url, options) {
        var notebook = this.props.app.notebook;

        var match = url.match(/^\/pages\/(.*)/);
        if (match) {
            // Parse node id.
            var nodeid = match[1];
            var node = notebook.getNode(nodeid);
            this.viewNode(node, options);
        }

        var match = url.match(/^nbk:\/\/\/(.*)/);
        if (match) {
            // Parse node id.
            var nodeid = match[1];
            var node = notebook.getNode(nodeid);
            this.viewNode(node, options);
        }
    },

    getNodePageUrl: function (node) {
        return '/pages/' + node.id;
    },

    onShowAttr: function (e) {
        e.preventDefault();
        if (this.state.currentNode)
            window.open(this.state.currentNode.url(), '_blank');
    },

    loadPage: function (node) {
        return node.readFile(node.PAGE_FILE).then(function (result) {
            return parsePageHtml(node, result).contents();
        });
    },

    savePage: function () {
        var node = this.state.currentNode;
        if (!node)
            return $.Deferred().resolve();

        var body = this.refs.pageEditor.getContent();
        var html = formatPageHtml(node, body);
        return node.writeFile(node.PAGE_FILE, html);
    },

    visitLink: function (url) {
        if (url.match(/^nbk:/)) {
            this.viewPageByUrl(url);
        } else {
            window.open(url, '_blank');
        }
    },

    focusSearch: function () {
        this.refs.search.focus();
    },

    searchTitle: function (query) {
        var notebook = this.props.app.notebook;
        return notebook.searchTitle(query);
    }
});


// Register key bindings to callbacks.
function KeyBinding() {
    this.bindings = {};

    // Add a new key binding.
    this.add = function (key, callback) {
        if (!(key in this.bindings))
            this.bindings[key] = [];
        this.bindings[key].push(callback);
    };

    // Remove a key binding.
    this.remove = function (key) {
        delete this.bindings[key];
    };

    // Clear all key bindings.
    this.clear = function () {
        this.bindings = {};
    };

    // Process a key press event.
    this.processEvent = function (event) {
        var hash = this.hashKeyEvent(event);

        if (hash in this.bindings) {
            var callbacks = this.bindings[hash];
            for (var i=0; i<callbacks.length; i++) {
                callbacks[i]();
            }
            event.preventDefault();
        }
    };

    // Return a hash of a key press event.
    this.hashKeyEvent = function (event) {
        var hash = '';
        if (event.ctrlKey || event.metaKey) {
            hash += 'ctrl ';
        }
        if (event.shiftKey) {
            hash += 'shift ';
        }

        var key = event.key;

        // Compatibility.
        if (key && key.match(/Left|Right|Up|Down/))
            key = 'Arrow' + key;

        hash += key;
        return hash;
    };
}


function KeepNoteApp() {
    this.notebook = null;
    this.view = null;

    this.init = function () {
        // Initial render.
        this.updateApp();

        // Register events.
        $(window).resize(this.queueUpdateApp.bind(this));

        // Fetch notebook.
        $.get('/notebook/nodes/').done(function (result) {
            var rootid = result.rootids[0];
            this.notebook = new NoteBook({rootid: rootid});
            this.notebook.on('change', this.onNoteBookChange, this);

            this.notebook.root.fetchExpanded().done(function () {
                // Process initial page url.
                this.view.viewPageByUrl(window.location.pathname);
            }.bind(this));
        }.bind(this));
    };

    this.onNoteBookChange = function () {
        this.queueUpdateApp();
    };

    this.updateApp = function () {
        this.view = React.render(
            React.createElement(KeepNoteView, {app: this}),
            $('#base').get(0)
        );
    };
    this.queueUpdateApp = _.debounce(this.updateApp.bind(this), 0);
}


// Define module exports.
if (typeof module !== 'undefined') {
    module.exports = {
        KeepNoteApp: KeepNoteApp
    };
}


},{"./notebook.js":3,"./treeview.jsx":4}],3:[function(require,module,exports){

// Notebook node model.
var Node = Backbone.Model.extend({

    PAGE_CONTENT_TYPE: 'text/xhtml+xml',
    PAGE_FILE: 'page.html',

    initialize: function () {
        this.notebook = null;
        this.parents = [];
        this.children = [];
        this.files = {};
        this.file = this.getFile('');
        this.ordered = false;
        this.fetched = false;

        this.on('change', this.onChange, this);
        this.on('change:childrenids', this.onChangeChildren, this);
        this.on('change:parentids', this.onChangeParents, this);
    },

    // TODO: make customizable.
    urlRoot: '/notebook/nodes/',
    idAttribute: 'nodeid',

    // Fetch node data.
    fetch: function (options) {
        var result = Node.__super__.fetch.call(this, options);
        return result.done(function () {
            this.fetched = true;

            this.onChangeChildren();
            this.onChangeParents();
        }.bind(this));
    },

    // Fetch node data only if not already fetched.
    ensureFetched: function () {
        var defer = $.Deferred();
        if (!this.fetched)
            defer = this.fetch();
        else
            defer.resolve();
        return defer;
    },

    onChange: function () {
    },

    // Allocate children nodes.
    onChangeChildren: function () {
        // Allocate and register new children.
        var childrenIds = this.get('childrenids') || [];
        var hasOrderLoaded = true;
        this.children = [];
        for (var i=0; i<childrenIds.length; i++) {
            var child = this.notebook.getNode(childrenIds[i]);
            this.children.push(child);
            if (typeof child.get('order') === 'undefined') {
                hasOrderLoaded = false;
            }
        }

        // Sort children by their order.
        if (hasOrderLoaded)
            this.orderChildren(false);
    },

    // Allocate parent nodes.
    onChangeParents: function () {
        // Allocate and register new children.
        var parentIds = this.get('parentids') || [];
        this.parents = [];
        for (var i=0; i<parentIds.length; i++) {
            this.parents.push(this.notebook.getNode(parentIds[i]));
        }
    },

    _loadChildren: function () {
        var defers = [];

        for (var i=0; i<this.children.length; i++)
            defers.push(this.children[i].fetch());

        return $.when.apply($, defers);
    },

    // Fetch all children.
    fetchChildren: function (refetch) {
        var defer = $.Deferred();
        if (!this.fetched || refetch)
            defer = this.fetch();
        else
            defer.resolve();
        return defer
            .then(this._loadChildren.bind(this))
            .then(this.orderChildren.bind(this));
    },

    orderChildren: function (trigger) {
        if (typeof trigger === 'undefined')
            trigger = true;

        this.children.sort(function (node1, node2) {
            var val1 = (node1.get('order') || 0);
            var val2 = (node2.get('order') || 0);
            return val1 - val2;
        });

        // Update children ids.
        var childrenIds = [];
        for (var i=0; i<this.children.length; i++)
            childrenIds.push(this.children[i].id);
        this.set('childrenids', childrenIds);

        this.ordered = true;
        if (trigger)
            this.trigger('change');
    },

    // Recursively fetch all expanded nodes.
    fetchExpanded: function (expandAttr) {
        expandAttr = expandAttr || 'expanded';

        var defer = $.Deferred();

        // Fetch this node if needed.
        if (!this.fetched)
            defer = this.fetch();
        else
            defer.resolve();

        // Recursively fetch children.
        return defer.then(function () {
            if (this.get(expandAttr)) {
                var defers = [];
                for (var i=0; i<this.children.length; i++) {
                    defers.push(this.children[i].fetchExpanded());
                }

                // After all child load, order them.
                return $.when.apply($, defers).done(
                    this.orderChildren.bind(this)
                );
            }
        }.bind(this));
    },

    // Return true if this node is a descendent of ancestor.
    isDescendant: function(ancestor) {
        var ptr = this;
        while (true) {
            if (ptr === ancestor)
                return true;
            if (ptr.parents.length > 0)
                ptr = ptr.parents[0];
            else
                break;
        }
        return false;
    },

    isPage: function () {
        return this.get('content_type') === this.PAGE_CONTENT_TYPE;
    },

    fileUrl: function (filename) {
        return this.url() + '/' + filename;
    },

    pageUrl: function () {
        return this.fileUrl(this.PAGE_FILE);
    },

    payloadUrl: function () {
        return this.fileUrl(this.get('payload_filename'));
    },

    getFile: function (filename) {
        if (filename in this.files)
            return this.files[filename];

        var file = new NodeFile({
            node: this,
            path: filename
        });

        this.files[filename] = file;
        this.registerFile(file);

        return file;
    },

    registerFile: function (file) {
        file.on('change', function () {
            this.trigger('file-change');
        }, this);
        file.on('destroy', function () {
            this.onFileDestroy(file); }, this);
    },

    unregisterFile: function (file) {
        file.off('change', null, this);
        file.off('destroy', function () {
            this.onFileDestroy(file); }, this);
    },

    onFileDestroy: function (file) {
        this.unregisterFile(file);
    },

    _isDir: function (filename) {
        return filename.match(/\/$/);
    },

    writeFile: function (filename, content) {
        if (this._isDir(filename))
            throw 'Cannot write to a directory.';
        return $.post(this.fileUrl(filename), content);
    },

    readFile: function (filename) {
        if (this._isDir(filename))
            throw 'Cannot read from a directory.';
        return $.get(this.fileUrl(filename));
    },

    deleteFile: function (filename) {
        var file = this.getFile(filename);
        return file.destroy();
    },

    move: function (options) {
        return this.notebook.moveNode(this, options);
    }
});


// Notebook node file model.
var NodeFile = Backbone.Model.extend({

    initialize: function (options) {
        this.node = options.node;
        this.path = options.path || '';
        this.children = [];

        this.isDir = (this.path === '' ||
                      this.path.substr(-1) === '/');
    },

    url: function () {
        var parts = this.path.split('/');
        for (var i in parts)
            parts[i] = encodeURIComponent(parts[i]);
        return this.node.url() + '/' + parts.join('/');
    },

    basename: function () {
        if (this.path === '')
            return '';

        var parts = this.path.split('/');
        if (this.isDir)
            return parts[parts.length - 2];
        else
            return parts[parts.length - 1];
    },

    _allocateChildren: function (files) {
        this.trigger('removing-children', this);

        // Allocate and register new children.
        this.children = [];
        for (var i=0; i<files.length; i++)
            this.children.push(this.node.getFile(files[i]));

        this.trigger('adding-children', this);
    },

    fetch: function (options) {
        // Files do not have any meta data and nothing to fetch.
        if (!this.isDir)
            return $.Deferred().resolve();

        var result = Node.__super__.fetch.call(this, options);
        return result.done(function () {
            // Allocate children nodes.
            var files = this.get('files');
            this._allocateChildren(files);

            this.trigger('change');
        }.bind(this));
    },

    fetchChildren: function () {
        return this.fetch().then(function () {
            return this.children;
        }.bind(this));
    },

    getChildByName: function (name) {
        for (var i=0; i<this.children.length; i++) {
            var child = this.children[i];
            if (child.basename() === name)
                return child;
        }
        return null;
    },

    read: function () {
        if (!this.isDir)
            return $.get(this.url());
        else
            throw 'Cannot read from a directory';
    },

    write: function (data) {
        if (!this.isDir)
            return $.post(this.url(), data);
        else
            throw 'Cannot write to a directory';
    }
});


var NoteBook = Backbone.Model.extend({

    urlRoot: '/notebook/',

    initialize: function (options) {
        this.nodes = {};
        this.root = this.getNode(options.rootid);
    },

    fetch: function (options) {
        return this.root.fetch();
    },

    save: function () {
        return $.ajax({
            type: 'POST',
            url: this.urlRoot + '?save'
        });
    },

    search: function (query) {
        return $.ajax({
            type: 'POST',
            url: this.urlRoot + '?index',
            data: JSON.stringify(query),
            dataType: 'json'
        });
    },

    searchTitle: function (title) {
        return this.search(['search', 'title', title]);
    },

    // Return a node in the node cache.
    getNode: function (nodeid) {
        if (nodeid in this.nodes)
            return this.nodes[nodeid];

        var node = new Node({nodeid: nodeid});
        node.notebook = this;
        this.registerNode(node);

        return node;
    },

    fetchNode: function (nodeid) {
        var node = this.getNode(nodeid);
        return node.fetch();
    },

    // Register all callbacks for a node.
    registerNode: function (node) {
        this.nodes[node.id] = node;

        // Node listeners.
        node.on('change', function () {
            this.onNodeChange(node); }, this);
        node.on('destroy', function () {
            this.onNodeDestroy(node); }, this);
        node.on('file-change', function (file) {
            this.onFileChange(file); }, this);
    },

    // Unregister all callbacks for a node.
    unregisterNode: function (node) {
        node.off('change', null, this);
        node.off('destroy', null, this);
        delete this.nodes[node.id];
    },

    // Callback for when nodes change.
    onNodeChange: function (node) {
        this.trigger('node-change', this, node);
        this.trigger('change');
    },

    onNodeDestroy: function (node) {
        // TODO: don't rely on store to update children ids.
        // Refetch all parents.
        for (var i=0; i<node.parents.length; i++) {
            node.parents[i].fetch();
        }

        // TODO: decide what to do with children. Recurse?

        this.unregisterNode(node);
        this.trigger('change');
    },

    // Callback for when files change.
    onFileChange: function (file) {
        this.trigger('file-change', this, file);
        this.trigger('change');
    },

    newNode: function (parent, index) {
        var NEW_TITLE = 'New Page';
        var EMPTY_PAGE = '<html><body></body></html>';

        if (index === null || typeof index === 'undefined')
            index = parent.children.length;
        if (index > parent.children.length)
            index = parent.children.length;

        // Create new node.
        var childrenIds;
        var node = new Node({
            'content_type': this.root.PAGE_CONTENT_TYPE,
            'title': NEW_TITLE,
            'parentids': [parent.id],
            'childrenids': [],
            'order': index
        });
        node.notebook = this;
        return node.save().then(function (result) {
            node.id = result.nodeid;
            this.registerNode(node);

            // Create empty page.
            var file = node.getFile(node.PAGE_FILE);
            file.write(EMPTY_PAGE);

            // Adjust parent children ids.
            childrenIds = parent.get('childrenids').slice(0);
            childrenIds.splice(index, 0, node.id);

            // Update all children orders.
            return this.updateChildOrder(childrenIds);
        }.bind(this)).then(function () {
            return parent.save(
                {childrenids: childrenIds},
                {wait: true}
            ).then(function () {
                return parent.fetchChildren(true);
            }).then(function () {
                return node;
            });
        }.bind(this));
    },

    deleteNode: function (node) {
        return node.destroy();
    },

    moveNode: function(node, options) {
        var target = options.target;
        var relation = options.relation;
        var parent = options.parent;
        var index = options.index;

        // Determine parent and index.
        if (typeof parent !== 'undefined') {
            // Parent is given, determine index.
            if (index === null || typeof index === 'undefined')
                index = parent.children.length;
            if (index > parent.children.length)
                index = parent.children.length;

        } else if (typeof target === 'undefined') {
            // Without parent, target must be given.
            throw 'Target node must be given';

        } else if (relation === 'child') {
            // Move node to be the last child of target.
            parent = target;
            index = parent.children.length;

        } else if (relation === 'after' || relation === 'before') {
            // Move node to be sibling of target.
            parent = target;
            if (parent.parents.length > 0)
                parent = parent.parents[0];
            index = parent.children.indexOf(target);
            if (index === -1)
                index = parent.children.length;
            else if (relation === 'after')
                index++;

        } else {
            throw 'Unknown relation: ' + relation;
        }

        // Remove node from old location, use place holder null.
        var oldParent = node.parents[0];
        var oldChildrenIds = oldParent.get('childrenids').slice(0);
        var i = oldChildrenIds.indexOf(node.id);
        oldChildrenIds[i] = null;

        // Insert child into new parent.
        var childrenIds;
        if (parent === oldParent)
            childrenIds = oldChildrenIds;
        else
            childrenIds = parent.get('childrenids').slice(0);
        childrenIds.splice(index, 0, node.id);

        // Remove placeholder null.
        i = oldChildrenIds.indexOf(null);
        oldChildrenIds.splice(i, 1);

        // Save child.
        node.set({
            parentids: [parent.id]
        });
        return node.save().then(function () {
            // Update all sibling orders of new parent.
            // We can leave old parent's orders non-contiguous.
            return this.updateChildOrder(childrenIds);

        }.bind(this)).then(function () {
            // Save new parent children.
            var defer = parent.save(
                {childrenids: childrenIds},
                {wait: true}
            ).then(function () {
                return parent.fetchChildren(true);
            });

            // Save old parent children, if distinct.
            var defer2 = $.Deferred();
            if (parent !== oldParent) {
                defer2 = oldParent.save(
                    {childrenids: oldChildrenIds},
                    {wait: true}
                ).then(function () {
                    return oldParent.fetchChildren(true);
                });
            } else {
                defer2.resolve();
            }

            return $.when(defer, defer2);
        }.bind(this));
    },

    // Update the order attr for all children given by their sorting.
    updateChildOrder: function (childrenIds) {
        var defers = [];

        for (var i=0; i<childrenIds.length; i++) {
            var child = this.getNode(childrenIds[i]);
            if (typeof child === 'undefined')
                continue;

            defers.push(child.save({order: i}));
        }

        return $.when.apply($, defers);
    }
});


if (typeof module !== 'undefined') {
    module.exports.NoteBook = NoteBook;
}


},{}],4:[function(require,module,exports){

// Text that can be edited when clicked on.
var InplaceEditor = React.createClass({displayName: "InplaceEditor",
    getInitialState: function () {
        return {
            editing: false,
            select: false
        };
    },

    render: function () {
        if (this.state.editing) {
            return React.createElement("input", {type: "text", ref: "input", 
                    className: this.props.className, 
                    defaultValue: this.props.value, 
                    onBlur: this.onBlur, 
                    onKeyPress: this.onKeyPress, 
                    onKeyDown: this.onKeyDown});
        } else {
            return React.createElement("span", {className: this.props.className, 
                    onDoubleClick: this.onEdit}, 
              this.props.value
            );
        }
    },

    componentDidUpdate: function () {
        if (this.state.select) {
            $(this.refs.input.getDOMNode()).select();
            this.setState({select: false});
        }
    },

    onEdit: function (e) {
        e.preventDefault();
        this.setState({
            editing: true,
            select: true
        });
    },

    onBlur: function (e) {
        e.preventDefault();
        this.submit();
    },

    onKeyPress: function (e) {
        var ENTER = 13;
        switch (e.charCode) {
        case ENTER:
            e.preventDefault();
            this.submit();
            break;
        }

        e.stopPropagation();
    },

    onKeyDown: function (e) {
        var ESCAPE = 27;
        switch (e.keyCode) {
        case ESCAPE:
            e.preventDefault();
            this.cancel();
            break;
        }

        e.stopPropagation();
    },

    cancel: function () {
        this.setState({editing: false});
    },

    submit: function () {
        var value = $(this.refs.input.getDOMNode()).val();
        if (this.props.onSubmit)
            this.props.onSubmit(value);
        this.setState({editing: false});
    }
});


var NotebookTreeDrop = React.createClass({displayName: "NotebookTreeDrop",
    mixins: [ReactDND.DragDropMixin],

    statics: {
        configureDragDrop: function (register) {
            register('NODE', {
                dropTarget: {
                    canDrop: function (component, node) {
                        // Target node cannot be a child of node.
                        return !node.isDescendant(component.props.targetNode);
                    },
                    acceptDrop: function(component, node) {
                        node.move({
                            target: component.props.targetNode,
                            relation: component.props.relation
                        });
                    }
                }
            });
        }
    },

    render: function () {
        var style = {};

        if (this.props.relation === 'before') {
            style = {
                position: 'absolute',
                top: 0,
                left: 0,
                height: '20%',
                width: '100%'
            };
        } else if (this.props.relation === 'after') {
            style = {
                position: 'absolute',
                bottom: 0,
                left: 0,
                height: '20%',
                width: '100%'
            };
        } else if (this.props.relation === 'child') {
            style = {
                position: 'absolute',
                top: '20%',
                bottom: '20%',
                left: 0,
                height: '60%',
                width: '100%'
            };
        }

        //style['border'] = '1px solid orange';

        // Hovering.
        if (this.getDropState('NODE').isHovering) {
            style.backgroundColor = 'orange';
            style.opacity = .5;
        }

        if (this.getDropState('NODE').isDragging) {
            return React.createElement("div", React.__spread({},  this.dropTargetFor('NODE'), 
            {style: style}));
        } else {
            return React.createElement("span", null);
        }
    }
});


// Notebook tree component.
var NotebookTreeNode = React.createClass({displayName: "NotebookTreeNode",
    mixins: [ReactDND.DragDropMixin],

    getDefaultProps: function () {
        return {
            depth: 0,
            indent: 20,
            rowHeight: 20,
            sortColumn: null,
            sortDir: 1
        };
    },

    getInitialState: function () {
        var node = this.props.node;
        var expanded = node.get(this.props.expandAttr) || false;
        return {
            expanded: expanded
        };
    },

    statics: {
        // Configure drag-and-drop behavior.
        configureDragDrop: function(register) {
            register('NODE', {
                dragSource: {
                    beginDrag: function(component) {
                        return {
                            item: component.props.node
                        };
                    }
                }
            });
        }
    },

    render: function() {
        var node = this.props.node;

        // Sort function for child nodes.
        function cmpNodes(attr, direction) {
            return function (node1, node2) {
                var val1 = (node1.get(attr) || 0);
                var val2 = (node2.get(attr) || 0);
                if (val1 < val2) {
                    return -direction;
                } else if (val1 > val2) {
                    return direction;
                } else {
                    return 0;
                }
            };
        }

        // Get child nodes in sorted order.
        var childNodes = [];
        for (var i=0; i<node.children.length; i++) {
            var child = node.children[i];
            if (child.fetched) {
                childNodes.push(child);
            }
        }
        if (this.props.sortColumn)
            childNodes.sort(cmpNodes(this.props.sortColumn,
                                     this.props.sortDir));

        // Render children nodes.
        var children = [];
        for (var i=0; i<childNodes.length; i++) {
            var child = childNodes[i];
            children.push(
              React.createElement(NotebookTreeNode, {
               key: child.id, 
               ref: 'child-' + child.id, 
               node: child, 
               depth: this.props.depth + 1, 
               indent: this.props.indent, 
               currentNode: this.props.currentNode, 
               onViewNode: this.props.onViewNode, 
               expandAttr: this.props.expandAttr, 
               columns: this.props.columns}));
        }

        var displayChildren = (
            node.get(this.props.expandAttr) ? 'inline' : 'none');
        var indent = this.props.depth * this.props.indent;
        var nodeClass = 'node-tree-title';
        if (node === this.props.currentNode)
            nodeClass += ' active';

        // Build node title.
        var onNodeClick;
        if (node.get('payload_filename')) {
            // Attached file.
            onNodeClick = this.onPayloadClick;
        } else {
            // Regular node.
            onNodeClick = this.onPageClick;
        }

        // Build columns.
        var columns = [];
        for (var i=0; i<this.props.columns.length; i++) {
            var column = this.props.columns[i];
            var style = {
                float: 'left',
                width: column.width
            };
            var content = [];

            // First column has indenting and expander.
            if (i === 0) {
                style.paddingLeft = indent;

                content.push(React.createElement("a", {key: "1", className: "expand", 
                              onClick: this.toggleChildren, 
                              href: "javascript:;"}, "+"));
            }

            if (column.attr === 'title') {
                content.push(React.createElement(InplaceEditor, {key: "2", className: "title", 
                             value: node.get('title'), 
                             onSubmit: this.onRenameNode}));
            } else if (column.attr === 'created_time' ||
                       column.attr === 'modified_time') {
                var timeFormat = '%Y/%m/%d %I:%M:%S %p';
                var time = node.get(column.attr);
                var text = strftime(timeFormat, new Date(time * 1000));
                content.push(text);
            } else {
                content.push(node.get(column.attr));
            }

            columns.push(
                React.createElement("div", {key: i, className: "treeview-column", style: style}, 
                  content
                ));
        }

        return React.createElement("div", {className: "node-tree"}, 
          React.createElement("div", React.__spread({ref: "node", className: nodeClass, 
           onClick: onNodeClick, 
           style: {position: 'relative'}}, 
           this.dragSourceFor('NODE')), 

            React.createElement(NotebookTreeDrop, {
             relation: "before", 
             targetNode: node}), 

            React.createElement(NotebookTreeDrop, {
             relation: "child", 
             targetNode: node}), 

            React.createElement(NotebookTreeDrop, {
             relation: "after", 
             targetNode: node}), 

            React.createElement("div", {style: {height: this.props.rowHeight}}, columns)
          ), 

          React.createElement("div", {className: "children", style: {display: displayChildren}}, 
            children
          )
        );
    },

    // Toggle display of child nodes.
    toggleChildren: function (e) {
        e.preventDefault();
        e.stopPropagation();

        var expanded = !this.state.expanded;
        this.setState({expanded: expanded});
        if (expanded) {
            this.props.node.fetchChildren();
        }

        var attr = {};
        attr[this.props.expandAttr] = expanded;
        this.props.node.save(attr);
    },

    // View a node's page.
    onPageClick: function (e) {
        e.preventDefault();

        if (this.props.onViewNode)
            this.props.onViewNode(this.props.node);
    },

    // Open node attached file in new window.
    onPayloadClick: function (e) {
        e.preventDefault();

        window.open(this.props.node.payloadUrl(), '_blank');
    },

    // Rename a node title.
    onRenameNode: function (value) {
        var node = this.props.node;
        node.set('title', value);
        node.save();
    }
});


var TreeviewHeader = React.createClass({displayName: "TreeviewHeader",
    getDefaultProps: function () {
        return {
            sortColumn: null,
            sortDir: 0
        };
    },

    getInitialState: function () {
        return {
            sortColumn: this.props.sortColumn,
            sortDir: this.props.sortDir
        };
    },

    render: function () {
        // Build column headers.
        var columns = [];
        for (var i=0; i<this.props.columns.length; i++) {
            var column = this.props.columns[i];
            var style = {
                float: 'left',
                width: column.width
            };

            var sortIcon = null;
            if (column.attr === this.state.sortColumn) {
                if (this.state.sortDir === 1) {
                    sortIcon = 'V';
                } else if (this.state.sortDir === -1) {
                    sortIcon = '^';
                }
            }

            columns.push(React.createElement("div", {key: i, className: "treeview-header-column", 
                          style: style, 
                          onClick: this.onClickHeader.bind(null, column)}, 
              column.attr, 
              React.createElement("span", {style: {float: 'right'}}, sortIcon)
            ));
        }

        return React.createElement("div", {className: "treeview-header", 
                style: {height: this.props.height}}, columns);
    },

    onClickHeader: function (column, event) {
        event.preventDefault();
        event.stopPropagation();
        var sortDir = this.state.sortDir;

        if (column.attr === this.state.sortColumn) {
            // Cycle through sort direction.
            if (sortDir === 1)
                sortDir = -1;
            else if (sortDir === -1)
                sortDir = 0;
            else
                sortDir = 1;
        } else {
            // Sort assending for new column.
            sortDir = 1;
        }

        this.setState({
            sortColumn: column.attr,
            sortDir: sortDir
        });

        if (this.props.onSort) {
            this.props.onSort(column.attr, sortDir);
        }
    }
});


var NotebookTree = React.createClass({displayName: "NotebookTree",
    getDefaultProps: function () {
        return {
            node: null,
            currentNode: null,
            expandAttr: 'expanded',
            showHeaders: false,
            size: [300, 300],
            columns: [{
                attr: 'title',
                width: 300
            }]
        };
    },

    getInitialState: function () {
        return {
            scrolled: false  // User has scrolled.
        };
    },

    render: function () {
        var headers = null;
        var headersHeight = 20;
        var viewSize = [this.props.size[0], this.props.size[1]];

        var sortColumn = 'order';
        var sortDir = 1;
        if (this.props.showHeaders) {
            viewSize[1] -= headersHeight;
            var node = this.props.node;
            if (node) {
                sortColumn = node.get('info_sort') || 'order';
                sortDir = node.get('info_sort_dir');
                if (sortDir !== 1 && sortDir !== -1)
                    sortDir = 1;
            }

            headers = React.createElement(TreeviewHeader, {
              height: headersHeight, 
              sortColumn: sortColumn, 
              sortDir: sortDir, 
              columns: this.props.columns, 
              onSort: this.onColumnSort});
        }

        return React.createElement("div", {onKeyDown: this.onKeyDown, tabIndex: "1"}, 
            headers, 
            React.createElement("div", {ref: "scrollPane", style: {
              overflow: 'auto',
              width: viewSize[0],
              height: viewSize[1]}}, 
              React.createElement(NotebookTreeNode, {
               ref: "root", 
               node: this.props.node, 
               currentNode: this.props.currentNode, 
               onViewNode: this.props.onViewNode, 
               expandAttr: this.props.expandAttr, 
               sortColumn: sortColumn, 
               sortDir: sortDir, 
               columns: this.props.columns})
            )
          );
    },

    componentDidMount: function () {
        // Install scroll listener.
        $(this.refs.scrollPane.getDOMNode()).on('scroll', this.onScroll);

        this.scrollToNode(this.props.currentNode);
    },

    componentDidUpdate: function (prevProps, prevState) {
        var scrolled = this.state.scrolled;

        // If a new node is selected, then reset scrolled state.
        if (prevProps.currentNode != this.props.currentNode) {
            this.setState({scrolled: false});
            scrolled = false;
        }

        // Autoscroll to current node, if user hasn't scrolled yet.
        if (!scrolled) {
            this.scrollToNode(this.props.currentNode);
        }
    },

    scrollToNode: function (node) {
        if (!node)
            return;

        // Recursively search for component with desired node.
        function find(component) {
            if (component.props.node === node)
                return component;

            for (var childName in component.refs) {
                if (childName.match(/^child-/)) {
                    var result = find(component.refs[childName]);
                    if (result)
                        return result;
                }
            }
        }

        // Scroll to desired node.
        var component = find(this.refs.root);
        if (component) {
            this.scrollTo(
                this.refs.scrollPane.getDOMNode(),
                component.refs.node.getDOMNode(),
                true);
        }
    },

    autoScrolled: 0,

    onScroll: function (event) {
        if (!this.autoScrolled) {
            this.setState({scrolled: true});
        }
    },

    // Autoscroll to position 'top'.
    autoScrollTop: function (scrollPane, top) {
        if (scrollPane.scrollTop() !== top) {
            this.autoScrolled++;
            scrollPane.scrollTop(top);
            setTimeout(function () {
                this.autoScrolled--;
            }.bind(this), 0);
        }
    },

    scrollTo: function (pane, element, auto) {
        pane = $(pane);
        element = $(element);
        var paneHeight = pane.height();
        var viewTop = pane.scrollTop();
        var viewBottom = viewTop + paneHeight;

        var offset = element.offset();
        var elementTop = offset.top - pane.offset().top + viewTop;
        var elementBottom = elementTop + element.height();

        if (elementTop < viewTop || elementBottom > viewBottom) {
            // Autoscroll if out of view.
            if (auto)
                this.autoScrollTop(pane, elementTop);
            else
                pane.scrollTop(elementTop);
        }
    },

    onKeyDown: function (event) {
        if (event.key === 'Backspace') {
            if (this.props.onDeleteNode)
                this.props.onDeleteNode(this.props.currentNode);
            event.preventDefault();
            event.stopPropagation();
        }
    },

    onColumnSort: function (attr, sortDir) {
        var node = this.props.node;
        if (node) {
            if (sortDir === 0) {
                attr = 'order';
                sortDir = 1;
            }
            node.save({
                'info_sort': attr,
                'info_sort_dir': sortDir
            });
        }
    }
});


// Exports.
if (typeof module !== 'undefined') {
    module.exports = {
        NotebookTree: NotebookTree
    };
}


},{}]},{},[1]);
