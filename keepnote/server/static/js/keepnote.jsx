
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


function isNodeDescendant(ancestor, node) {
    var ptr = node;
    while (true) {
        if (ptr == ancestor)
            return true;
        if (ptr.parents.length > 0)
            ptr = ptr.parents[0];
        else
            break;
    }
    return false;
}


var NotebookTreeDrop = React.createClass({
    mixins: [ReactDND.DragDropMixin],

    statics: {
        configureDragDrop: function (register) {
            register('NODE', {
                dropTarget: {
                    canDrop: function (component, node) {
                        // Target node cannot be a child of node.
                        return !isNodeDescendant(
                            node, component.props.targetNode);
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

        if (this.props.relation == 'before') {
            style = {
                position: 'absolute',
                top: 0,
                left: 0,
                height: '20%',
                width: '100%'
            };
        } else if (this.props.relation == 'after') {
            style = {
                position: 'absolute',
                bottom: 0,
                left: 0,
                height: '20%',
                width: '100%'
            };
        } else if (this.props.relation == 'child') {
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
            return <div {...this.dropTargetFor('NODE')}
            style={style}/>;
        } else {
            return <span></span>;
        }
    }
});


// Notebook tree component.
var NotebookTreeNode = React.createClass({
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
                    },
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
                if (val1 < val2)
                    return -direction;
                else if (val1 > val2)
                    return direction;
                else
                    return 0;
            }
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
              <NotebookTreeNode
               key={child.id}
               node={child}
               depth={this.props.depth + 1}
               indent={this.props.indent}
               currentNode={this.props.currentNode}
               onViewNode={this.props.onViewNode}
               expandAttr={this.props.expandAttr}
               columns={this.props.columns}/>);
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
            if (i == 0) {
                style.paddingLeft = indent;

                content.push(<a className="expand"
                              onClick={this.toggleChildren}
                              href="javascript:;">+</a>);
            }

            if (column.attr == 'title') {
                content.push(<InplaceEditor className="title"
                             value={node.get('title')}
                             onSubmit={this.onRenameNode}/>);
            } else if (column.attr == 'created_time' ||
                       column.attr == 'modified_time') {
                var timeFormat = '%Y/%m/%d %I:%M:%S %p';
                var time = node.get(column.attr);
                var text = strftime(timeFormat, new Date(time * 1000));
                content.push(text);
            } else {
                content.push(node.get(column.attr));
            }

            columns.push(<div style={style}>{content}</div>);
        }

        return <div className="node-tree">
          <div className={nodeClass}
           onClick={onNodeClick}
           style={{position: 'relative'}}
           {...this.dragSourceFor('NODE')}>

            <NotebookTreeDrop
             relation="before"
             targetNode={node}/>

            <NotebookTreeDrop
             relation="child"
             targetNode={node}/>

            <NotebookTreeDrop
             relation="after"
             targetNode={node}/>

            <div style={{height: this.props.rowHeight}}>{columns}</div>
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
        node.set("title", value);
        node.save();
    }
});


var TreeviewHeader = React.createClass({
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
            if (column.attr == this.state.sortColumn) {
                if (this.state.sortDir == 1) {
                    sortIcon = 'V';
                } else if (this.state.sortDir == -1) {
                    sortIcon = '^';
                }
            }

            columns.push(<div key={i} className="treeview-header-column"
                          style={style}
                          onClick={this.onClickHeader.bind(null, column)}>
              {column.attr}
              <span style={{float: 'right'}}>{sortIcon}</span>
            </div>);
        }

        return <div className='treeview-header'
                style={{height: this.props.height}}>{columns}</div>;
    },

    onClickHeader: function (column, event) {
        event.preventDefault();
        event.stopPropagation();
        var sortDir = this.state.sortDir;

        if (column.attr == this.state.sortColumn) {
            // Cycle through sort direction.
            if (sortDir == 1)
                sortDir = -1
            else if (sortDir == -1)
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


var NotebookTree = React.createClass({
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
                if (sortDir != 1 && sortDir != -1)
                    sortDir = 1;
            }

            headers = <TreeviewHeader
              height={headersHeight}
              sortColumn={sortColumn}
              sortDir={sortDir}
              columns={this.props.columns}
              onSort={this.onColumnSort}/>;
        }

        return <div onKeyDown={this.onKeyDown} tabIndex="1">
            {headers}
            <div style={{
              overflow: 'auto',
              width: viewSize[0],
              height: viewSize[1]}}>
              <NotebookTreeNode
               node={this.props.node}
               currentNode={this.props.currentNode}
               onViewNode={this.props.onViewNode}
               expandAttr={this.props.expandAttr}
               sortColumn={sortColumn}
               sortDir={sortDir}
               columns={this.props.columns}/>
            </div>
          </div>;
    },

    onKeyDown: function (event) {
        if (event.key == 'Backspace') {
            if (this.props.onDeleteNode)
                this.props.onDeleteNode(this.props.currentNode);
            event.preventDefault();
            event.stopPropagation();
        }
    },

    onColumnSort: function (attr, sortDir) {
        var node = this.props.node;
        if (node) {
            if (sortDir == 0) {
                attr = 'order';
                sortDir = 1;
            }
            node.save({
                info_sort: attr,
                info_sort_dir: sortDir
            });
        }
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
        var size = this.props.size;
        var pageEditor = this.refs.pageEditor.getDOMNode();

        // Add editor buttons.
        var toolbar = this.refs.toolbar.getDOMNode();
        var toolbarContent = $($("#page-toolbar-template").html()).children();
        $(toolbar).append(toolbarContent);

        // Setup editor.
        this.editor = new wysihtml5.Editor('page-editor', {
            toolbar: 'page-toolbar',
            parserRules:  wysihtml5ParserRules
        });

        // Attach listener to link double clicks.
        var that = this;
        $(pageEditor).on('dblclick', 'a', function (event) {
            event.preventDefault();
            if (that.props.onVisitLink)
                that.props.onVisitLink($(this).attr('href'));
        });

        // TODO: move this into render.
        // Align dialog to bottom of editor.
        var toolbarHeight = 25;
        var rect = pageEditor.getBoundingClientRect();
        var linkDialog = $("[data-wysihtml5-dialog=createLink]");
        linkDialog.css({
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
        $("body").keypress(bindings.processEvent.bind(bindings));
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
        bindings.add("ctrl s", this.save);
        bindings.add("ctrl k", this.focusSearch);
        bindings.add("ctrl n", this.newNode);
        bindings.add("ctrl shift N", this.newChildNode);
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
        ]
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

        return notebook.newNode(parent, index).done(function (node) {
            this.viewNode(node);
        }.bind(this));
    },

    newChildNode: function () {
        var notebook = this.props.app.notebook;
        if (!notebook)
            return;

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

        // Save history.
        if (!skipHistory) {
            var state = {
                currentNodeId: node.id
            };
            var pageUrl = this.getNodePageUrl(node);
            window.history.pushState(state, node.get("title"), pageUrl);
        }

        // TODO: need to expand listview to node.
        this.getVisibleTreeNode(node).done(function (treeNode) {
            this.setState({
                currentTreeNode: treeNode,
                currentNode: node
            });

            // Expand for listview.
            treeNode.fetchExpanded('expanded2');

            // Load node in page editor.
            if (node.isPage()) {
                this.loadPage(node).done(function (content) {
                    this.refs.pageEditor.setContent(content);
                }.bind(this));
            } else {
                // Node is a directory. Display blank page.
                this.refs.pageEditor.clear();
            }
        }.bind(this));
    },

    getVisibleTreeNode: function (node) {
        // Get path to root.
        var rootPath = [node];

        // Recursively fetch the root path.
        function visit(ptr) {
            var defer = $.Deferred();
            if (!ptr.fetched)
                defer = ptr.fetch();
            else
                defer.resolve();

            defer.then(function () {
                var defer = $.Deferred();
                if (ptr.parents.length == 0) {
                    defer.resolve();
                    return defer;
                } else {
                    ptr = ptr.parents[0];
                    rootPath.push(ptr);
                    defer.resolve(ptr);
                    return defer.then(visit);
                }
            });
            return defer;
        }

        return visit(node).then(function () {
            // Find first selected or visible node in root path.
            rootPath.reverse();
            var treeNode = null;
            for (var i=0; i<rootPath.length; i++) {
                treeNode = rootPath[i];
                if (!treeNode.get('expanded') ||
                    treeNode == this.state.currentTreeNode)
                    break;
            }
            return treeNode;
        }.bind(this));
    },

    viewTreeNode: function (node, options) {
        this.setState({
            currentTreeNode: node,
            currentNode: node
        });
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
        return "/pages/" + node.id;
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
            var rootid = result["rootids"][0];
            this.notebook = new NoteBook({rootid: rootid});
            this.notebook.on("change", this.onNoteBookChange, this);

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


// Callback for when JSX file is compiled.
if (onKeepNoteComplied)
    onKeepNoteComplied();
