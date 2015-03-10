var child_process = require('child_process');
var del = require('del');
var gulp = require('gulp');
var bowerNormalizer = require('gulp-bower-normalize');
var mainBowerFiles = require('main-bower-files');

function buildBowerFiles() {
    var stream = gulp.src(mainBowerFiles(),
                    {base: './bower_components'})
        .pipe(bowerNormalizer({bowerJson: './bower.json'}))
        .pipe(gulp.dest('./keepnote/server/static/thirdparty/'));

    stream.on('end', function () {
        var patcher = child_process.spawn('patch', [
            '-N',
            'keepnote/server/static/thirdparty/xmldom/js/dom.js',
            'setup/xmldom.patch'
        ]);
    });
}

gulp.task('bower-files', buildBowerFiles);

gulp.task('clean', function (cb) {
    del(['keepnote/server/static/thirdparty/**'], cb);
});

gulp.task('default', ['bower-files']);
