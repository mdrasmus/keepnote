var del = require('del');
var gulp = require('gulp');

var mainBowerFiles = require('main-bower-files');
var bowerNormalizer = require('gulp-bower-normalize');

function buildBowerFiles() {
    return gulp.src(mainBowerFiles(),
                    {base: './bower_components'})
        .pipe(bowerNormalizer({bowerJson: './bower.json'}))
        .pipe(gulp.dest("./keepnote/server/static/thirdparty/"));
}

gulp.task('bower-files', buildBowerFiles);

gulp.task('clean', function (cb) {
    del(['keepnote/server/static/thirdparty/**'], cb);
});

gulp.task('default', ['bower-files']);
