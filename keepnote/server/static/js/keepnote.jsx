
// Parse a page's HTML into DOM elements.
function parsePageHtml(node, html) {
    // Parse page html.
    var parser = new DOMParser();
    var htmlDoc = parser.parseFromString(html, "text/html");
    var body = $(htmlDoc.getElementsByTagName("body"));

    convertHtmlForDisplay(node, body);

    return body.contents();
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


var PageToolbar = React.createClass({
    render: function () {
        return <div className="page-toolbar" id="page-toolbar">
            <a onClick={this.props.onSavePage} href="#">save</a>
            <a data-wysihtml5-command="bold">bold</a>
            <a data-wysihtml5-command="italic">italic</a>
            <a data-wysihtml5-command="formatBlock" data-wysihtml5-command-value="h1">H1</a>
            <a data-wysihtml5-command="formatBlock" data-wysihtml5-command-value="p">P</a>
        </div>;
    }
});


var NotebookTree = React.createClass({
    getInitialState: function () {
        var node = this.props.node;
        var expanded = node.get("expanded") || false;

        return {
            firstOpen: true,
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
            children.push(
                <li key={child.id}>
                  <NotebookTree
                   node={child}
                   currentNode={this.props.currentNode}
                   onViewNode={this.props.onViewNode} /></li>);
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

        // Fetch children if node is expanded.
        if (node.get("expanded") && this.state.firstOpen) {
            setTimeout(function () {
                node.fetchChildren();
                this.setState({
                    firstOpen: false,
                    expanded: node.get("expanded")
                });
            }.bind(this), 0);
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


var KeepNoteView = React.createClass({
    getInitialState: function () {
        return {
            currentNode: null
        };
    },

    render: function () {
        var app = this.props.app;
        var notebook = app.notebook;

        var treeWidth = 400;
        var toolbarHeight = 25;

        //var offset = [this.pageScrollOffset[0], 0];
        var windowSize = [$(window).width(), $(window).height()];
        var appSize = [windowSize[0] - 4, windowSize[1] - 2];
        var treeSize = [treeWidth, appSize[1]];

        var pageWidth = windowSize[0] - treeSize[0] - 4;
        var toolbarSize = [pageWidth, toolbarHeight];
        var pageSize = [pageWidth, appSize[1]];

        return <div id="app">
          <div id="treeview-pane"
            style={{width: treeSize[0], height: treeSize[1]}} >
            <NotebookTree
             node={notebook.root}
             currentNode={this.state.currentNode}
             onViewNode={this.viewNode}
            />
          </div>
          <div id="page-pane"
        style={{width: pageSize[0], height: pageSize[1]}} >
            <PageToolbar
             style={{width: toolbarSize[0], height: toolbarSize[1]}}
             onSavePage={this.onSavePage} />
            <div id="page-editor" data-placeholder=""></div>
          </div>
        </div>;
    },

    viewNode: function (node) {
        //window.history.pushState({}, node.get("title"), node.url());
        this.setState({currentNode: node});

        this.loadPage(node).done(function (content) {
            // Load page view;
            var pageView = $("#page-editor");
            pageView.empty();
            pageView.append(content);
        });
    },

    onSavePage: function (e) {
        e.preventDefault();
        this.savePage();
    },

    loadPage: function (node) {
        return node.readFile(node.PAGE_FILE).then(function (result) {
            return parsePageHtml(node, result);
        });
    },

    savePage: function () {
        var node = this.state.currentNode;

        var htmlHeader = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n' +
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>');
        var htmlFooter = '</body></html>';

        var editor = $("#page-editor");
        var body = editor.clone();
        convertHtmlForStorage(node, body);

        var serializer = new XMLSerializer();
        var xhtml = [];
        body.contents().each(function (i) {
            xhtml.push(serializer.serializeToString($(this).get(0)));
        });
        xhtml = xhtml.join('');

        var pageContents = htmlHeader + xhtml + htmlFooter;

        return node.writeFile(node.PAGE_FILE, pageContents);
    }
});


function KeepNoteApp() {
    this.notebook = null;
    this.editor = null;
    this.currentNode = null;

    this.init = function () {
        this.updateApp();

        $(window).resize(this.queueUpdateApp.bind(this));

        $.get('/notebook/').done(function (result) {
            var rootid = result["rootids"][0];
            this.notebook = new NoteBook({rootid: rootid});
            this.notebook.on("change", this.onNoteBookChange.bind(this));
            this.notebook.fetch();
        }.bind(this));
    };

    this.initEditor = function () {
        if (this.editor)
            return;
        this.editor = new wysihtml5.Editor('page-editor', {
            toolbar: 'page-toolbar',
            parserRules:  wysihtml5ParserRules
        });
    };

    this.onNoteBookChange = function () {
        this.queueUpdateApp();
    };

    this.updateApp = function () {
        if (!this.notebook)
            return;
        React.render(
            <KeepNoteView app={this} />,
            $('#base').get(0),
            this.initEditor.bind(this)
        );
    };
    this.queueUpdateApp = _.debounce(this.updateApp.bind(this), 0);

    this.updateView = function () {
        // Render GUI.
        React.render(
            <NotebookTree node={this.notebook.root} />,
            $('#treeview-pane #notebook').get(0)
        );
    };
    this.queueUpdateView = _.debounce(this.updateView.bind(this), 0);
}


// Callback for when JSX file is compiled.
if (onKeepNoteComplied)
    onKeepNoteComplied();
