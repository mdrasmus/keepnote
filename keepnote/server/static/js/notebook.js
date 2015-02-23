
// Notebook node model.
var Node = Backbone.Model.extend({

    PAGE_CONTENT_TYPE: "text/xhtml+xml",
    PAGE_FILE: "page.html",

    initialize: function (options) {
        this.notebook = options.notebook || null;
        this.files = {};
        this.file = this.getFile('');
        this.children = [];
        this.ordered = false;
        this.fetched = false;
    },

    urlRoot: '/notebook',

    // Allocate children nodes.
    _allocateChildren: function (childrenIds) {
        this.trigger("removing-children", this);

        // Allocate and register new children.
        this.children = [];
        for (var i=0; i<childrenIds.length; i++) {
            var child = this.notebook.getNode(childrenIds[i]);
            child.on("destroy", this.onChildDestroy.bind(this));
            this.children.push(child);
        }

        this.trigger("adding-children", this);
    },

    // Fetch node data.
    fetch: function (options) {
        var result = Node.__super__.fetch.call(this, options);
        return result.then(function () {
            this.fetched = true;

            // Allocate children nodes.
            var childrenIds = this.get('childrenids');
            if (typeof(childrenIds) == "undefined")
                childrenIds = [];
            this._allocateChildren(childrenIds);

            this.trigger('change');
        }.bind(this));
    },

    _loadChildren: function () {
        var defers = [];

        for (var i=0; i<this.children.length; i++)
            defers.push(this.children[i].fetch());

        return $.when.apply($, defers);
    },

    // Fetch all children.
    fetchChildren: function () {
        if (!this.fetched || this.ordered)
            return;
        return this._loadChildren().then(
            this.orderChildren.bind(this)
        );
    },

    orderChildren: function () {
        function cmp(node1, node2) {
            return node1.get('order') - node2.get('order');
        }
        this.children.sort(cmp);
        this.ordered = true;
        this.trigger('change');
    },

    onChildDestroy: function (child) {
        // Remove child from children.
        this.children = _.filter(this.children,
                                 function(o) { return o !== child; });
        this.trigger('change');
    },

    // Recursively fetch all expanded nodes.
    fetchExpanded: function () {
        var defer = $.Deferred();

        // Fetch this node if needed.
        if (!this.fetched)
            defer = this.fetch();
        else
            defer.resolve();

        // Recursively fetch children.
        return defer.done(function () {
            if (this.get('expanded')) {
                var defers = [];
                for (var i=0; i<this.children.length; i++) {
                    defers.push(this.children[i].fetchExpanded());
                }

                // After all child load, order them.
                $.when.apply($, defers).done(
                    this.orderChildren.bind(this)
                );
            }
        }.bind(this));
    },

    isPage: function () {
        return this.get("content_type") == this.PAGE_CONTENT_TYPE;
    },

    fileUrl: function (filename) {
        return this.url() + "/" + filename;
    },

    pageUrl: function () {
        return this.fileUrl(this.PAGE_FILE);
    },

    payloadUrl: function () {
        return this.fileUrl(this.get("payload_filename"));
    },

    getFile: function (filename) {
        if (filename in this.files)
            return this.files[filename];

        var file = new NodeFile({
            node: this,
            path: filename
        });
        this.files[filename] = file;
        this.registerFile(file);

        return file;
    },

    registerFile: function (file) {
        file.on("change", function () {
            this.trigger('file-change');
        }, this);
        file.on("destroy", function () {
            this.onFileDestroy(file); }, this);
    },

    unregisterFile: function (file) {
        file.off("change", null, this);
        file.off("destroy", function () {
            this.onFileDestroy(file); }, this);
    },

    onFileDestroy: function (file) {
        this.unregisterFile(file);
    },

    _isDir: function (filename) {
        return filename.match(/\/$/);
    },

    writeFile: function (filename, content) {
        if (this._isDir(filename))
            throw "Cannot write to a directory.";
        return $.post(this.fileUrl(filename), content);
    },

    readFile: function (filename) {
        if (this._isDir(filename))
            throw "Cannot read from a directory.";
        return $.get(this.fileUrl(filename));
    },

    deleteFile: function (filename) {
        var file = this.getFile(filename);
        return file.destroy();
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

        // Allocate and register new children.
        this.children = [];
        for (var i=0; i<files.length; i++)
            this.children.push(this.node.getFile(files[i]));

        this.trigger("adding-children", this);
    },

    fetch: function (options) {
        // Files do not have any meta data and nothing to fetch.
        if (!this.isDir)
            return;

        var result = Node.__super__.fetch.call(this, options);
        return result.done(function () {
            // Allocate children nodes.
            var files = this.get('files');
            this._allocateChildren(files);

            this.trigger('change');
        }.bind(this));
    },

    fetchChildren: function () {
        return this.fetch().then(function () {
            return this.children;
        }.bind(this));
    },

    getChildByName: function (name) {
        for (var i=0; i<this.children.length; i++) {
            var child = this.children[i];
            if (child.basename() == name)
                return child;
        }
        return null;
    },

    read: function () {
        if (!this.isDir)
            return $.get(this.url());
        else
            throw "Cannot read from a directory";
    },

    write: function (data) {
        if (!this.isDir)
            return $.post(this.url(), data);
        else
            throw "Cannot write to a directory";
    }
});


var NoteBook = Backbone.Model.extend({
    initialize: function (options) {
        this.nodes = {};
        this.root = this.getNode(options.rootid);
    },

    fetch: function (options) {
        return this.root.fetch();
    },

    // Return a node in the node cache.
    getNode: function (nodeid) {
        if (nodeid in this.nodes)
            return this.nodes[nodeid];

        var node = new Node({
            id: nodeid,
            notebook: this
        });
        this.registerNode(node);

        return node;
    },

    fetchNode: function (nodeid) {
        var node = this.getNode(nodeid);
        return node.fetch();
    },

    // Register all callbacks for a node.
    registerNode: function (node) {
        this.nodes[node.id] = node;

        // Node listeners.
        node.on("change", function () {
            this.onNodeChange(node); }, this);
        node.on("file-change", function (file) {
            this.onFileChange(file); }, this);
    },

    // Unregister all callbacks for a node.
    unregisterNode: function (node) {
        node.off("change", null, this);

        this.unregisterFile(node.file);
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
    }
});
