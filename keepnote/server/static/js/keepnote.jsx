
// Parse a page's HTML into DOM elements.
function parsePageHtml(node, html) {
    // Parse page html.
    var parser = new DOMParser();
    var htmlDoc = parser.parseFromString(html, "text/html");
    var body = $(htmlDoc.getElementsByTagName("body"));

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
    var baseUrl = node.url() + "/";

    // Adjust all relative image urls for display.
    body.find("img").each(function (i) {
        var img = $(this);
        var src = img.attr("src");

        if (!isAbsoluteUrl(src))
            img.attr("src", baseUrl + src);
    });
}


function convertHtmlForStorage(node, body) {
    var baseUrl = node.url() + "/";

    // Adjust all img urls for storage.
    body.find("img").each(function (i) {
        var img = $(this);
        var src = img.attr("src");

        // TODO: prevent image loading.
        // Strip baseUrl if present.
        if (src.substr(0, baseUrl.length) == baseUrl)
            img.attr("src", src.substr(baseUrl.length));

        // Remove unneeded title attribute.
        img.removeAttr("title");
    });
}


var NotebookTreeRaw = React.createClass({
    getInitialState: function () {
        var node = this.props.node;
        var expanded = node.get("expanded") || false;
        return {
            firstOpen: !node.fetched,
            expanded: expanded,
            filesExpanded: false
        };
    },

    render: function() {
        var node = this.props.node;

        // Get children.
        var children = [];
        for (var i=0; i<node.children.length; i++) {
            var child = node.children[i];
            if (child.fetched) {
                children.push(
                  <li key={child.id}>
                   <NotebookTreeRaw
                    node={child}
                    currentNode={this.props.currentNode}
                    onViewNode={this.props.onViewNode} /></li>);
            }
        }

        var displayChildren = (this.state.expanded ? "inline" : "none");
        var displayFiles = (this.state.filesExpanded ? "block" : "none");
        var nodeClass = "node-tree";
        if (node == this.props.currentNode)
            nodeClass += " active";

        // Build node title.
        var title = <span className="title">{node.get('title')}</span>;
        if (node.isPage()) {
            // Notebook page.
            title = <a href="#" onClick={this.onPageClick}>{title}</a>;
        } else if (node.get("payload_filename")) {
            // Attached file.
            title = <a href={node.payloadUrl()} target="_blank">{title}</a>;
        }

        return <div className={nodeClass}>
          <a className="expand" onClick={this.toggleChildren} href="#">+</a>
          {title}
          [<a href={node.url()}>attr</a>]&nbsp;
          [<a onClick={this.toggleFiles} href="#">files</a>]

          <div className="files" style={{display: displayFiles}}>
            <NotebookFile
             file={node.file}
             showFilename={false}
             expanded={true} />
          </div>

          <div className="children" style={{display: displayChildren}}>
            <ul>
              {children}
            </ul>
          </div>
        </div>;
    },

    toggleChildren: function (e) {
        e.preventDefault();

        var expanded = !this.state.expanded;
        this.setState({expanded: expanded});
        if (expanded) {
            this.props.node.fetchChildren();
        }
    },

    toggleFiles: function (e) {
        e.preventDefault();

        var expanded = !this.state.filesExpanded;
        this.setState({filesExpanded: expanded});
        if (expanded)
            this.props.node.file.fetch();
    },

    onPageClick: function (e) {
        e.preventDefault();

        if (this.props.onViewNode)
            this.props.onViewNode(this.props.node);
    }
});


// Text that can be edited when clicked on.
var InplaceEditor = React.createClass({
    getInitialState: function () {
        return {
            editing: false,
            select: false
        };
    },

    render: function () {
        if (this.state.editing) {
            return <input type="text" ref="input"
                    className={this.props.className}
                    defaultValue={this.props.value}
                    onBlur={this.onBlur}
                    onKeyPress={this.onKeyPress}
                    onKeyDown={this.onKeyDown}/>;
        } else {
            return <span className={this.props.className}
                    onDoubleClick={this.onEdit}>
              {this.props.value}
            </span>;
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
        if (e.charCode == ENTER) {
            e.preventDefault();
            this.submit();
        }
    },

    onKeyDown: function (e) {
        var ESCAPE = 27;
        if (e.which == ESCAPE) {
            e.preventDefault();
            this.cancel();
        }
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


// Notebook tree component.
var NotebookTree = React.createClass({
    getDefaultProps: function () {
        return {
            depth: 0,
            indent: 20
        };
    },

    getInitialState: function () {
        var node = this.props.node;
        var expanded = node.get("expanded") || false;
        return {
            firstOpen: !node.fetched,
            expanded: expanded,
            filesExpanded: false
        };
    },

    render: function() {
        var node = this.props.node;

        // Get children.
        var children = [];
        for (var i=0; i<node.children.length; i++) {
            var child = node.children[i];
            if (child.fetched) {
                children.push(
                  <NotebookTree
                   key={child.id}
                   node={child}
                   depth={this.props.depth + 1}
                   indent={this.props.indent}
                   currentNode={this.props.currentNode}
                   onViewNode={this.props.onViewNode}/>);
            }
        }

        var displayChildren = (this.state.expanded ? "inline" : "none");
        var indent = this.props.depth * this.props.indent;
        var nodeClass = "node-tree-title";
        if (node == this.props.currentNode)
            nodeClass += " active";

        // Build node title.
        var onNodeClick;
        if (node.get("payload_filename")) {
            // Attached file.
            onNodeClick = this.onPayloadClick;
        } else {
            // Regular node.
            onNodeClick = this.onPageClick;
        }

        return <div className="node-tree">
          <div className={nodeClass} onClick={onNodeClick}>
            <div style={{paddingLeft: indent}}>
              <a className="expand" onClick={this.toggleChildren} href="javascript:;">+</a>
              <InplaceEditor className="title"
               value={node.get('title')}
               onSubmit={this.onRenameNode}/>
            </div>
          </div>

          <div className="children" style={{display: displayChildren}}>
            {children}
          </div>
        </div>;
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
        node.set("title", value);
        node.save();
    }
});


var NotebookFile = React.createClass({
    getDefaultProps: function () {
        return {
            showFilename: true,
            expanded: false
        };
    },

    getInitialState: function () {
        return {
            expanded: this.props.expanded
        };
    },

    render: function () {
        var file = this.props.file;

        // Populate child list.
        var children = [];
        var fileChildren = file.children;
        for (var i=0; i<fileChildren.length; i++) {
            var child = fileChildren[i];
            children.push(<li key={i}><NotebookFile file={child} /></li>);
        }

        var displayChildren = (this.state.expanded ? "block" : "none");

        var filenameNode = null;
        if (this.props.showFilename) {
            // Render filename link.
            var filename = file.basename() + (file.isDir ? '/' : '');

            var onClick = null;
            var href = "#";
            if (file.isDir) {
                onClick = this.toggleChildren;
            } else {
                href = file.url();
            }

            filenameNode = <a key="0" className="filename"
                            onClick={onClick} href={href}>{filename}</a>;
        }

        return <div style={this.props.style}>
            {filenameNode}
            <ul style={{display: displayChildren}}>
              {children}
            </ul>
          </div>;
    },

    toggleChildren: function (e) {
        e.preventDefault();

        var expanded = !this.state.expanded;
        this.setState({expanded: expanded});
        if (expanded)
            this.props.file.fetch();
    }
});


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
        // Add editor buttons.
        var toolbar = this.refs.toolbar.getDOMNode();
        var toolbarContent = $($("#page-toolbar-template").html()).children();
        $(toolbar).append(toolbarContent);

        // Setup editor.
        this.editor = new wysihtml5.Editor('page-editor', {
            toolbar: 'page-toolbar',
            parserRules:  wysihtml5ParserRules
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


var KeepNoteView = React.createClass({
    getInitialState: function () {
        return {
            currentNode: null,
            bindings: new KeyBinding()
        };
    },

    componentDidMount: function () {
        var bindings = this.state.bindings;
        $("body").keypress(bindings.processEvent.bind(bindings));
        this.initKeyBindings();
    },

    initKeyBindings: function () {
        var bindings = this.state.bindings;
        bindings.add("ctrl s", this.save);
        bindings.add("ctrl n", this.newNode);

        // TODO: bind to treeview instead.
        //bindings.add("Backspace", this.deleteNode);
    },

    render: function () {
        var app = this.props.app;
        var root = app.notebook ? app.notebook.root : null;

        var treeWidth = 300;

        //var offset = [this.pageScrollOffset[0], 0];
        var windowSize = [$(window).width(), $(window).height()];
        var appSize = [windowSize[0] - 4, windowSize[1] - 2];
        var treeSize = [treeWidth, appSize[1]];

        var pageWidth = windowSize[0] - treeSize[0] - 4;
        var pageSize = [pageWidth, appSize[1]];

        var viewtree = root ?
            <NotebookTree
             node={root}
             currentNode={this.state.currentNode}
             onViewNode={this.viewNode}/> :
            <div/>;

        return <div id="app">
          <div id="treeview-pane"
            style={{width: treeSize[0], height: treeSize[1]}}>
            {viewtree}
          </div>
          <div id="page-pane"
           style={{width: pageSize[0], height: pageSize[1]}}>
            <PageEditor ref="pageEditor"
             size={pageSize}
             onShowAttr={this.onShowAttr}/>
          </div>
        </div>;
    },

    save: function () {
        this.savePage();
    },

    newNode: function () {
        var notebook = this.props.app.notebook;
        if (!notebook)
            return;

        var root = notebook.root;
        var node = this.state.currentNode;
        var parent = null;
        var index = null;

        if (!node || node == root) {
            parent = root;
            index = null;
        } else {
            parent = node.parents[0];
            index = (node.get('order') || 0) + 1;
        }

        return notebook.newNode(parent, index);
    },

    deleteNode: function () {
        var notebook = this.props.app.notebook;
        var node = this.state.currentNode;
        if (node)
            notebook.deleteNode(node);
    },

    viewNode: function (node) {
        //window.history.pushState({}, node.get("title"), node.url());
        this.setState({currentNode: node});

        if (node.isPage()) {
            this.loadPage(node).done(function (content) {
                this.refs.pageEditor.setContent(content);
            }.bind(this));
        } else {
            // Node is a directory. Display blank page.
            this.refs.pageEditor.clear();
        }
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
            return;

        var body = this.refs.pageEditor.getContent();
        var html = formatPageHtml(node, body);
        return node.writeFile(node.PAGE_FILE, html);
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
    }

    // Remove a key binding.
    this.remove = function (key) {
        delete this.bindings[key];
    }

    // Clear all key bindings.
    this.clear = function () {
        this.bindings = {};
    }

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
    }

    // Return a hash of a key press event.
    this.hashKeyEvent = function (event) {
        var hash = "";
        if (event.ctrlKey || event.metaKey) {
            hash += 'ctrl ';
        }
        if (event.shiftKey) {
            hash += 'shift ';
        }

        var key = event.key;

        // Compatibility.
        if (key.match(/Left|Right|Up|Down/))
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
            var rootid = result["rootids"][0];
            this.notebook = new NoteBook({rootid: rootid});
            this.notebook.on("change", this.onNoteBookChange, this);

            this.notebook.root.fetchExpanded();
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


// Callback for when JSX file is compiled.
if (onKeepNoteComplied)
    onKeepNoteComplied();
