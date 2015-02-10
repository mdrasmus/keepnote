
// Notebook node model.
var Node = Backbone.Model.extend({

    initialize: function (options) {
        this.file = new NodeFile({
            node: this,
            path: ''
        });
        this.children = [];
        this.ordered = false;
        this.fetched = false;
    },

    urlRoot: '/notebook',

    _allocateChildren: function (childrenIds) {
        this.trigger("removing-children", this);

        // Build lookup of existing children.
        var lookup = {};
        for (var i=0; i<this.children.length; i++) {
            var child = this.children[i];
            lookup[child.id] = child;
        }

        // Allocate and register new children.
        this.children = [];
        for (var i=0; i<childrenIds.length; i++) {
            var childId = childrenIds[i];

            // Try to reuse existing children if possible.
            var child = (childId in lookup ?
                         lookup[childId] :
                         new Node({id: childId}));
            this.children.push(child);
        }

        this.trigger("adding-children", this);
    },

    fetch: function (options) {
        var result = Node.__super__.fetch.call(this, options);
        return result.done(function () {
            this.fetched = true;

            // Allocate children nodes.
            var childrenIds = this.get('childrenids');
            if (typeof(childrenIds) == "undefined")
                childrenIds = [];
            this._allocateChildren(childrenIds);

            this.trigger('change');
        }.bind(this));
    },

    fetchChildren: function () {
        var defers = []

        for (var i in this.children)
            defers.push(this.children[i].fetch());

        return $.when.apply($, defers);
    },

    orderChildren: function () {
        var that = this;

        if (!this.fetched || this.ordered)
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
        this.children = [];

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

    _allocateChildren: function (files) {
        this.trigger("removing-children", this);

        // Build lookup of existing children.
        var lookup = {};
        for (var i=0; i<this.children.length; i++) {
            var child = this.children[i];
            lookup[child.path] = child;
        }

        // Allocate and register new children.
        this.children = [];
        for (var i=0; i<files.length; i++) {
            var file = files[i];

            // Try to reuse existing children if possible.
            var child = (file in lookup ?
                         lookup[file] :
                         new NodeFile({
                             node: this.node,
                             path: file
                         }));
            this.children.push(child);
        }

        this.trigger("adding-children", this);
    },


    fetch: function (options) {
        var result = Node.__super__.fetch.call(this, options);
        return result.done(function () {
            // Allocate children nodes.
            var files = this.get('files');
            this._allocateChildren(files);

            this.trigger('change');
        }.bind(this));
    },

    fetchChildren: function () {
        var that = this;
        return this.fetch().then(function () {
            return that.children;
        });
    }
});


var NoteBook = Backbone.Model.extend({
    initialize: function (options) {
        this.root = new Node({id: options.rootid});
        this.registerNode(this.root);
    },

    fetch: function (options) {
        return this.root.fetch();
    },

    // Register all callbacks for a node.
    registerNode: function (node) {
        // Node listeners.
        node.on("change", function () {
            this.onNodeChange(node); }, this);
        node.on("adding-children", this.onAddingChildren, this);
        node.on("removing-children", this.onRemovingChildren, this);

        this.registerFile(node.file);
    },

    // Unregister all callbacks for a node.
    unregisterNode: function (node) {
        node.off("adding-children", null, this);
        node.off("removing-children", null, this);
        node.off("change", null, this);

        this.unregisterFile(node.file);
    },

    // Register all callbacks for a file.
    registerFile: function (file) {
        file.on("change", function () {
            this.onFileChange(file); }, this);
        file.on("adding-children", this.onAddingFileChildren, this);
        file.on("removing-children", this.onRemovingFileChildren, this);
    },

    // Unregister all callbacks for a file.
    unregisterFile: function (file) {
        file.off("change", null, this);
        file.off("adding-children", null, this);
        file.off("removing-children", null, this);
    },

    // Callback for when nodes change.
    onNodeChange: function (node) {
        this.trigger("node-change", this, node);
        this.trigger("change");
    },

    // Callback for when files change.
    onFileChange: function (file) {
        this.trigger("file-change", this, file);
        this.trigger("change");
    },

    // Callback for when a node loads its children.
    onAddingChildren: function (node) {
        for (var i=0; i<node.children.length; i++) {
            var child = node.children[i];
            this.registerNode(child);
        }
    },

    // Callback for when a node unloads its children.
    onRemovingChildren: function (node) {
        for (var i=0; i<node.children.length; i++) {
            var child = node.children[i];
            this.unregisterNode(child);
        }
    },

    // Callback for when a file loads its children.
    onAddingFileChildren: function (file) {
        for (var i=0; i<file.children.length; i++) {
            var child = file.children[i];
            this.registerFile(child);
        }
    },

    // Callback for when a file unloads its children.
    onRemovingFileChildren: function (file) {
        for (var i=0; i<file.children.length; i++) {
            var child = file.children[i];
            this.unregisterFile(child);
        }
    },
});
