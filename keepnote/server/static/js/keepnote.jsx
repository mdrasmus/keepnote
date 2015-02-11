function viewPage(node) {
    var baseUrl = node.url() + "/";

    $.ajax(node.pageUrl()).done(function (result) {
        //window.history.pushState({}, node.get("title"), node.url());

        // Parse page html.
        var parser = new DOMParser();
        var htmlDoc = parser.parseFromString(result, "text/html");
        var body = $(htmlDoc.getElementsByTagName("body"));

        // Adjust all img urls.
        body.find("img").each(function (i) {
            var img = $(this);
            img.attr("src", baseUrl + img.attr("src"));
        });

        // Load page.
        var pageView = $("#page-view");
        pageView.empty();
        pageView.append(body.contents());
    });
}


var KeepNoteView = React.createClass({
    render: function () {
        var windowSize = [$(window).width(), $(window).height()];
        //var offset = [this.pageScrollOffset[0], 0];
        var treeWidth = 400;
        var appHeight = windowSize[1] - 4;
        var pageWidth = windowSize[0] - treeWidth - 4;

        return <div id="app">
          <div id="treeview-pane">
            <div id="notebook"
             style={{height: appHeight, width: treeWidth}}></div>
          </div>
          <div id="page-pane">
            <div id="page-view"
             style={{height: appHeight, width: pageWidth}}></div>
          </div>
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
                <li key={child.id}><NotebookTree node={child} /></li>);
        }

        //var onPageClick = function (e) { this.
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

        return <div>
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
        viewPage(this.props.node);
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
