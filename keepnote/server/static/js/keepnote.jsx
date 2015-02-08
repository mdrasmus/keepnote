
var NotebookTree = React.createClass({

    getInitialState: function () {
        return {expanded: false};
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

        var onExpand = function () { this.toggleChildren(); }.bind(this);
        var displayChildren = (this.state.expanded ? "inline" : "none");

        return <div>
          <a className="expand" onClick={onExpand} href="#">+</a>
          <span className="title">{node.get('title')}</span>
          <a className="attr" href={node.url()}>attr</a> &nbsp;
          <a className="files" href="#">files</a>
          <div className="files-list"></div>
          <div className="children" style={{display: displayChildren}}>
            <ul>
              {children}
            </ul>
          </div>
        </div>;
    },

    toggleChildren: function (show) {
        if (typeof(show) == 'undefined')
            show = !this.state.expanded;
        this.setState({expanded: show});

        if (show) {
            this.props.node.fetchChildren();
            this.props.node.orderChildren();
        }
    },
});
