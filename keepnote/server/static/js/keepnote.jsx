
// Parse a page's HTML into DOM elements.
function parsePageHtml(node, html) {
    var baseUrl = node.url() + "/";

    // Parse page html.
    var parser = new DOMParser();
    var htmlDoc = parser.parseFromString(html, "text/html");
    var body = $(htmlDoc.getElementsByTagName("body"));

    // Adjust all img urls.
    body.find("img").each(function (i) {
        var img = $(this);
        img.attr("src", baseUrl + img.attr("src"));
    });

    return body.contents();
}


var PageToolbar = React.createClass({
    render: function () {
        return <div className="page-toolbar">
          <a onClick={this.props.onViewPage} href="#">view</a> &nbsp;
          <a onClick={this.props.onEditPage} href="#">edit</a> &nbsp;
          <a onClick={this.props.onSavePage} href="#">save</a>
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
                  <NotebookTree node={child}
                   onViewNode={this.props.onViewNode} /></li>);
        }

        var displayChildren = (this.state.expanded ? "inline" : "none");
        var displayFiles = (this.state.filesExpanded ? "block" : "none");

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

        return <div className="node-tree">
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

        console.log(">>", this.props.onViewNode);

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
            editing: false
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

        var displayPageView = (!this.state.editing ? "inline" : "none");
        var displayPageEditor = (this.state.editing ? "inline" : "none");

        return <div id="app">
          <div id="treeview-pane"
            style={{width: treeSize[0], height: treeSize[1]}} >
            <NotebookTree
             node={notebook.root}
             onViewNode={this.onViewNode}
            />
          </div>
          <div id="page-pane"
           style={{width: pageSize[0], height: pageSize[1]}} >
            <PageToolbar
             style={{width: toolbarSize[0], height: toolbarSize[1]}}
             onViewPage={this.onViewPage}
             onEditPage={this.onEditPage}
             onSavePage={this.onSavePage} />
            <div id="page-view" style={{display: displayPageView}}></div>
            <div id="page-editor" style={{display: displayPageEditor}}>
              <div id="toolbar">
                <a data-wysihtml5-command="bold">bold</a>
                <a data-wysihtml5-command="italic">italic</a>
                <a data-wysihtml5-command="formatBlock" data-wysihtml5-command-value="h1">H1</a>
                <a data-wysihtml5-command="formatBlock" data-wysihtml5-command-value="p">P</a>
              </div>

              <div id="editor" data-placeholder="Go on, start editing..."></div>
            </div>
          </div>
        </div>;
    },

    onViewNode: function (node) {
        app.viewNode(node);
    },

    onViewPage: function (e) {
        e.preventDefault();
        this.setState({editing: false});
    },

    onEditPage: function (e) {
        e.preventDefault();
        this.setState({editing: true});
    },

    onSavePage: function (e) {
        e.preventDefault();

        var htmlHeader = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n' +
            '<html xmlns="http://www.w3.org/1999/xhtml">\n' +
            '<head>\n' +
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n' +
            '<title>distributions</title>\n' +
                '</head><body>\n');
        var htmlFooter = (
            '</body></html>');

        var editor = $("#editor");
        var pageContents = htmlHeader + editor.html() + htmlFooter;
        var node = this.props.app.currentNode;

        $.post(node.pageUrl(), pageContents);
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
        this.editor = new wysihtml5.Editor('editor', {
            toolbar: 'toolbar',
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

    this.viewNode = function (node) {
        console.log("node", node);
        this.currentNode = node;

        $.ajax(node.pageUrl()).done(function (result) {
            //window.history.pushState({}, node.get("title"), node.url());

            console.log(">", node, result);

            // Load page view;
            var pageView = $("#page-view");
            var content = parsePageHtml(node, result);
            pageView.empty();
            pageView.append(content);

            /*
            // Load page.
            var pageEditor = $("#page-editor");
            var content = parsePageHtml(node, result);
            pageEditor.empty();
            pageEditor.append(content);
            */
        });
    };
}


// Callback for when JSX file is compiled.
if (onKeepNoteComplied)
    onKeepNoteComplied();
