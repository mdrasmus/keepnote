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


var PageToolbar = React.createClass({
    render: function () {
        return (<div className="page-toolbar" id="page-toolbar">
          <a href="javascript:;" onClick={this.props.onShowAttr}>attr</a>
        </div>);
    }
});


var PageEditor = React.createClass({
    render: function () {
        var size = this.props.size;
        var toolbarHeight = 25;
        var toolbarSize = [size[0], toolbarHeight];
        var editorSize = [size[0], size[1] - toolbarHeight];

        return (<div>
          <PageToolbar ref="toolbar"
           style={{width: toolbarSize[0], height: toolbarSize[1]}}
           onShowAttr={this.props.onShowAttr}/>
          <div id="page-editor" ref="pageEditor"
           style={{width: editorSize[0], height: editorSize[1]}}/>
        </div>);
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


var SearchBox = React.createClass({
    render: function () {
        return <div className="search"><input ref="search" type="text"/></div>;
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


var KeepNoteView = React.createClass({
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
            <NotebookTree
             node={root}
             currentNode={this.state.currentTreeNode}
             onViewNode={this.viewTreeNode}
             onDeleteNode={this.deleteNode}
             expandAttr="expanded"
             size={treeSize}/> :
            <div/>;

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
            <NotebookTree
             node={this.state.currentTreeNode}
             currentNode={this.state.currentNode}
             onViewNode={this.viewNode}
             onDeleteNode={this.deleteNode}
             expandAttr="expanded2"
             columns={listviewColumns}
             showHeaders={true}
             size={listviewSize}/> :
            <div/>;

        return <div id="app">
          <div id="topbar"
           style={{width: topbarSize[0], height: topbarSize[1]}}>
            <SearchBox ref="search"
             search={this.searchTitle}
             onViewNodeId={this.viewNodeId}/>
          </div>
          <div id="treeview-pane" tabIndex="1"
           style={{width: treeSize[0], height: treeSize[1]}}>
            {treeview}
          </div>
          <div id="page-pane"
           style={{width: rightSize[0], height: rightSize[1]}}>
           <div id="listview-pane" tabIndex="1"
            style={{width: listviewSize[0], height: listviewSize[1]}}>
            {listview}
           </div>
            <PageEditor ref="pageEditor"
             size={pageSize}
             onShowAttr={this.onShowAttr}
             onVisitLink={this.visitLink}/>
          </div>
        </div>;
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
            <KeepNoteView app={this} />,
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
