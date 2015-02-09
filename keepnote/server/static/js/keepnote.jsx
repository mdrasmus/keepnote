
var NotebookTree = React.createClass({
    getInitialState: function () {
        return {
            expanded: false,
            filesExpanded: false
        };
    },

    componentDidMount: function () {
        //forceUpdate will be called at most once every second
        var threshold = 0;
        this._boundForceUpdate = _.throttle(
            this.forceUpdate.bind(this, null), threshold);
        this.props.node.on("all", this._boundForceUpdate, this);
    },

    componentWillUnmount: function () {
        this.props.node.off("all", this._boundForceUpdate);
    },

    render: function() {
        var node = this.props.node;

        // Get children
        var children = [];
        for (var i=0; i<node.children.length; i++) {
            var child = node.children[i];
            children.push(
                <li key={child.id}><NotebookTree node={child} /></li>);
        }

        var onExpand = function (e) { this.toggleChildren(e); }.bind(this);
        var onFileClick = function (e) { this.toggleFiles(e); }.bind(this);
        var displayChildren = (this.state.expanded ? "inline" : "none");
        var displayFiles = (this.state.filesExpanded ? "block" : "none");

        return <div>
          <a className="expand" onClick={onExpand} href="#">+</a>
          <span className="title">{node.get('title')}</span>
          <a className="attr" href={node.url()}>attr</a> &nbsp;
          <a className="files" onClick={onFileClick} href="#">files</a>

          <NotebookFile
            file={node.file}
            showFilename={false}
            expanded={true}
            style={{display: displayFiles}} />

          <div className="children" style={{display: displayChildren}}>
            <ul>
              {children}
            </ul>
          </div>
        </div>;
    },

    toggleChildren: function (e) {
        e.preventDefault();

        var show = !this.state.expanded;
        this.setState({expanded: show});

        if (show) {
            this.props.node.fetchChildren();
            this.props.node.orderChildren();
        }

        return false;
    },

    toggleFiles: function (e) {
        e.preventDefault();

        var expanded = !this.state.filesExpanded;
        this.setState({filesExpanded: expanded});
        if (expanded)
            this.props.node.file.fetch();
    },

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

    componentDidMount: function () {
        //forceUpdate will be called at most once every second
        var threshold = 0;
        this._boundForceUpdate = _.throttle(
            this.forceUpdate.bind(this, null), threshold);
        this.props.file.on("all", this._boundForceUpdate, this);
    },

    componentWillUnmount: function () {
        this.props.file.off("all", this._boundForceUpdate);
    },

    render: function () {
        var file = this.props.file;

        // Populate child list.
        var children = [];
        var fileChildren = file.getChildren();
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
                onClick = function (e) {
                    return this.toggleChildren(e);
                }.bind(this);
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

        var show = !this.state.expanded;
        this.setState({expanded: show});
        if (show)
            this.props.file.fetch();
    }
});