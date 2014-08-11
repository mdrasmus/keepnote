
// Notebook node model.
var Node = Backbone.Model.extend({

    initialize: function (options) {
        this.file = new NodeFile({
            node: this,
            path: ''
        });
        this.children = [];
        this.ordered = false;

        this.on('change', this.onChanged, this);
    },

    urlRoot: '/notebook',

    fetch: function (options) {
        var that = this;
        var result = Node.__super__.fetch.call(this, options);
        return result.done(function () {
            // Allocate children nodes.
            var childrenIds = that.get('childrenids');
            that.children = [];
            if (typeof(childrenIds) != "undefined") {
                for (var i in childrenIds) {
                    that.children.push(new Node({id: childrenIds[i]}));
                }
            }

            that.trigger('change');
        });
    },

    fetchChildren: function () {
        var defers = []

        for (var i in this.children)
            defers.push(this.children[i].fetch());
        
        return $.when.apply($, defers);
    },

    orderChildren: function () {
        var that = this;

        if (this.ordered)
            return;

        function cmp(node1, node2) {
            return node1.get('order') - node2.get('order');
        }

        return this.fetchChildren().then(function () {
            that.children.sort(cmp);
            that.ordered = true;
            that.trigger('change');
        });
    }

});


// Notebook node file model.
var NodeFile = Backbone.Model.extend({
    
    initialize: function (options) {
        this.node = options.node;
        this.path = options.path || '';

        this.isDir = (this.path == '' || 
                      this.path.substr(-1) == '/');
    },

    url: function () {
        var parts = this.path.split('/');
        for (var i in parts)
            parts[i] = encodeURIComponent(parts[i]);
        return this.node.url() + '/' + parts.join('/');
    },

    basename: function () {
        if (this.path == '')
            return '';

        var parts = this.path.split('/');
        if (this.isDir)
            return parts[parts.length - 2];
        else
            return parts[parts.length - 1];
    },

    getChildren: function () {
        var children = [];
        var files = this.get('files');

        if (!files)
            return children;
        
        for (var i in files) {
            children.push(new NodeFile({
                node: this.node,
                path: files[i]
            }));
        }

        return children;
    },

    fetchChildren: function () {
        var that = this;
        return this.fetch().then(function () {
            return that.getChildren();
        });
    }
});


var NodeView = Backbone.View.extend({

    initialize: function () {
        this.childrenExpanded = false;
        this.filesExpanded = false;

        this.model.on('change', this.render, this);
    },

    render: function () {
        var that = this;

        this.$el.html(
            '<a class="expand" href="#">+</a> ' +
            '<span class="title"></span> ' +
            '<a class="attr" href="#">attr</a> ' + 
            '<a class="files" href="#">files</a> ' + 
            '<div class="files-list"></div>' +
            '<div class="children"></div>'
        );
        this.children = this.$el.find('.children');
        var filesElm = this.$el.find('.files-list').get(0);

        // Events.
        this.$el.find('.title').text(this.model.get('title'));
        this.$el.find('.expand').click(function () { that.toggleChildren(); });
        this.$el.find('.attr').attr('href', this.model.url());
        this.$el.find('.files').click(function () { 
            that.toggleFiles(); return false;
        });

        // Children node subviews.
        if (!this.childrenExpanded)
            this.children.hide();
        
        var list = $("<ul>");
        this.children.append(list);
        for (var i in this.model.children) {
            var node = this.model.children[i];
            var nodeView = new NodeView({model: node});
            var li = $('<li></li>');
            li.append(nodeView.render().el);
            list.append(li);
        }

        // Files subview.
        this.files = new NodeFileView({
            model: this.model.file,
            showFilename: false
        });
        this.files.setElement(filesElm);
        if (!this.filesExpanded)
            this.files.$el.hide();

        return this;
    },

    toggleChildren: function () {
        this.children.toggle();

        this.childrenExpanded = this.children.is(':visible');
        if (this.childrenExpanded)
            this.model.orderChildren();
    },

    toggleFiles: function () {
        this.files.$el.toggle();

        this.filesExpanded = this.files.$el.is(':visible');
        if (this.filesExpanded)
            this.model.file.fetch();
    }

});


var NodeFileView = Backbone.View.extend({
    
    initialize: function (options) {
        this.showFilename = options.showFilename;
        if (typeof(this.showFilename) == 'undefined')
            this.showFilename = true;
        this.model.on('change', this.render, this);

        this.subviews = [];
        this.expanded = !this.showFilename;
    },

    render: function () {
        var that = this;
        this.childList = $('<ul></ul>');
        
        // Populate child list.
        var children = this.model.getChildren();
        for (var i in children) {
            var child = children[i];
            var subview = new NodeFileView({model: child});
            this.subviews.push(subview);
            this.childList.append(subview.render().el);
        }

        this.$el.empty();
        if (this.showFilename) {
            // Render filename link.
            var filename = this.model.basename();
            if (this.model.isDir)
                filename += '/';
            this.$el.html('<a class="filename" href="#">' + filename + '</a>');

            var link = this.$el.find('.filename');
            if (that.model.isDir) {
                link.click(function () {
                    that.toggleChildren();
                    return false;
                });
            } else {
                link.attr('href', that.model.url());
            }
        }

        if (!this.expanded)
            this.childList.hide();

        this.$el.append(this.childList);
        return this;
    },

    toggleChildren: function () {
        var that = this;
        this.childList.toggle();

        this.expanded = this.childList.is(':visible');
        if (this.expanded)
            this.model.fetch();
    }
});
