
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
        if (this.state.expanded) {
            for (var i=0; i<node.children.length; i++) {
                var child = node.children[i];
                children.push(
                    <li key={i}><NotebookTree node={child} /></li>);
                child.fetch();
            }
        }

        var onExpand = function () { this.toggleChildren(); }.bind(this);

        return <div>
          <a className="expand" onClick={onExpand} href="#">+</a>
          <span className="title">{node.get('title')}</span>
          <a className="attr" href={node.url()}>attr</a> &nbsp;
          <a className="files" href="#">files</a>
          <div className="files-list"></div>
          <div className="children">
            <ul>
              {children}
            </ul>
          </div>
        </div>;
    },

    toggleChildren: function (show) {
        if (typeof(show) == 'undefined') {
            this.setState({expanded: !this.state.expanded});
        } else {
            this.setState({expanded: show});
        }

        if (this.state.expanded)
            this.props.node.orderChildren();
    },
});
