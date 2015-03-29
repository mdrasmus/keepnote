
var BUILTIN_ICONS_URL = '/static/images/node_icons/';

// Guess the open version of an icon filename.
function guessOpenIconFilename(filename) {
    var ext = filename.match(/\.[^\.]*/);
    if (ext) {
        ext = ext[0];
        var prefix = filename.slice(0, -ext.length);
        return prefix + '-open' + ext;
    } else {
        return filename;
    }
}


/*
  Lookup full filename of a icon from a notebook and builtins.

  Return null if not found
  notebook: can be null
  basename: basename of icon filename.
*/
function lookupIconFilename(notebook, basename) {
    var defer = $.Deferred();

    notebook.root.ensureFetched().then(function () {
        // Lookup in notebook icon store.
        var iconFilename = notebook.getIconFilename(basename);
        return notebook.root.hasFile(iconFilename).then(function (exists) {
            if (exists) {
                var url = notebook.root.fileUrl(iconFilename);
                return defer.resolve(url);
            } else {
                return $.Deferred().reject();
            }
        });
    }).fail(function () {
        // Lookup in builtins.
        var url = BUILTIN_ICONS_URL + basename;
        $.ajax({
            type: 'HEAD',
            url: url
        }).then(function () {
            return defer.resolve(BUILTIN_ICONS_URL + basename);
        }).fail(function () {
            return defer.reject();
        });
    });

    // Lookup in mimetypes.

    return defer;
}


// content-type --> [close-icon, open-icon]
var DEFAULT_NODE_ICONS = {
    'text/xhtml+xml': ['note.png', 'note.png'],
    'application/x-notebook-dir': ['folder.png', 'folder-open.png'],
    'application/x-notebook-trash': ['trash.png', 'trash.png'],
    'application/x-notebook-unknown': ['note-unknown.png', 'note-unknown.png']
};


/*
  Get icon filenames for notebook node.
*/
function getNodeIconBasenames(node) {
    var basenames = {
        close: [],
        open: []
    };

    // Get icon based on node attributes.
    if (node.has('icon_open')) {
        basenames.open.push(node.get('icon_open'));
    }
    if (node.has('icon')) {
        var icon = node.get('icon');
        basenames.close.push(icon);
        basenames.open.push(guessOpenIconFilename(icon));
        basenames.open.push(icon);
    }

    // Get icons based on content_type.
    if (node.get('content_type') in DEFAULT_NODE_ICONS) {
        var names = DEFAULT_NODE_ICONS[node.get('content_type')];
        basenames.close.push(names[0]);
        basenames.open.push(names[1]);
    }

    // Add defaults.
    basenames.close.push('note-unknown.png');
    basenames.open.push('note-unknown.png');

    return basenames;
}

/*
def get_node_icon_filenames_basenames(node):

    # TODO: merge with get_node_icon_filenames?

    notebook = node.get_notebook()

    # get default basenames
    basenames = list(get_default_icon_basenames(node))
    filenames = get_default_icon_filenames(node)

    # load icon
    if node.has_attr("icon"):
        # use attr
        basename = node.get_attr("icon")
        filename = lookup_icon_filename(notebook, basename)
        if filename:
            filenames[0] = filename
            basenames[0] = basename

    # load icon with open state
    if node.has_attr("icon_open"):
        # use attr
        basename = node.get_attr("icon_open")
        filename = lookup_icon_filename(notebook, basename)
        if filename:
            filenames[1] = filename
            basenames[1] = basename
    else:
        if node.has_attr("icon"):

            # use icon to guess open icon
            basename = guess_open_icon_filename(node.get_attr("icon"))
            filename = lookup_icon_filename(notebook, basename)
            if filename:
                filenames[1] = filename
                basenames[1] = basename
            else:
                # use icon as-is for open icon if it is specified
                basename = node.get_attr("icon")
                filename = lookup_icon_filename(notebook, basename)
                if filename:
                    filenames[1] = filename
                    basenames[1] = basename

    return basenames, filenames
*/


if (typeof module !== 'undefined') {
    module.exports = {
        lookupIconFilename: lookupIconFilename,
        getNodeIconBasenames: getNodeIconBasenames
    };
}
