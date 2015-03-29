
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


var NotebookTreeDrop = React.createClass({
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

                content.push(<a key="1" className="expand"
                              onClick={this.toggleChildren}
                              href="javascript:;">+</a>);
            }

            if (column.attr === 'title') {
                content.push(<InplaceEditor key="2" className="title"
                             value={node.get('title')}
                             onSubmit={this.onRenameNode}/>);
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
                <div key={i} className='treeview-column' style={style}>
                  {content}
                </div>);
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
        node.set('title', value);
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
            if (column.attr === this.state.sortColumn) {
                if (this.state.sortDir === 1) {
                    sortIcon = 'V';
                } else if (this.state.sortDir === -1) {
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
                if (sortDir !== 1 && sortDir !== -1)
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
