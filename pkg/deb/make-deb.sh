# Make debian packages for Keepnote

if [ $# -lt 1 ]; then
    echo "NEED TO GIVE VERSION NUMBER"
    exit 1
fi

# configure
export DEBFULLNAME="Matt Rasmussen"
export DEBEMAIL="rasmus@alum.mit.edu"
PKG_NAME=keepnote
PKG_VERSION="$1"


#=============================================================================
# variables

PKG_TAR=../../dist/${PKG_NAME}-${PKG_VERSION}.tar.gz
PKG_ORIG=${PKG_NAME}-${PKG_VERSION}.orig.tar.gz
PKG_DIR=${PKG_NAME}-${PKG_VERSION}
DATE=$(date -R)


# move into the directory of this script
cd $(dirname $0)

#=============================================================================
# other arguments

if [ $# -gt 1 ]; then

    if [ x"$2" == x"save_changelog" ]; then
	# save the last changelog for future releases
	cp $PKG_DIR/debian/changelog debian/changelog
	exit
    fi

    CHANGELOG_MSG="$2"
else
    CHANGELOG_MSG="Debian release of keepnote-${PKG_VERSION}"
fi


#=============================================================================
# process

# move source here
rm -rf $PKG_DIR
cp $PKG_TAR $PKG_ORIG
tar zxvf $PKG_ORIG

# copy in debian files
cp -r debian $PKG_DIR

# prepend changelog
cat > $PKG_DIR/debian/changelog <<EOF
${PKG_NAME} (${PKG_VERSION}-1) unstable; urgency=low

  * ${CHANGELOG_MSG}

 -- ${DEBFULLNAME} <${DEBEMAIL}>  ${DATE}
EOF
cat debian/changelog >> $PKG_DIR/debian/changelog


# make package
cd $PKG_DIR 
fakeroot make -f debian/rules binary


#=============================================================================
# make initial debian files

# OLD CODE
cat > /dev/null <<EOF
cd ${PKG_NAME}-${PKG_VERSION}
dh_make -c gpl -s -b
rm debian/*.ex debian/*.EX
rm debian/README.Debian
rm debian/dirs
#dch -e
EOF