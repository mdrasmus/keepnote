#
# Makefile for KeepNote
#
# common building tasks
#

PKG=keepnote
VERSION:=$(shell python -c 'import keepnote; print keepnote.PROGRAM_VERSION_TEXT')

# build programs
PYTHON=python2.5

# release filenames
SDIST_FILE=$(PKG)-$(VERSION).tar.gz
RPM_FILE=$(PKG)-$(VERSION)-1.noarch.rpm
EBUILD_FILE=$(PKG)-$(VERSION).ebuild
DEB_FILE=$(PKG)_$(VERSION)-1_all.deb
WININSTALLER_FILE=$(PKG)-$(VERSION).exe

# release file locations
SDIST=dist/$(SDIST_FILE)
RPM=dist/$(RPM_FILE)
DEB=dist/$(DEB_FILE)
EBUILD=dist/$(EBUILD_FILE)
WININSTALLER=dist/$(WININSTALLER_FILE)

# files to upload
UPLOAD_FILES=$(SDIST) $(RPM) $(DEB) $(EBUILD) $(WININSTALLER)

CODEQUALITY_FILES=\
	keepnote/*.py \
	keepnote/gui \
	tests/*.py \
	tests/gui/*.py

TMP_FILES=MANIFEST

# windows related variables
WINDIR=dist/$(PKG)-$(VERSION).win
WINEXE=$(WINDIR)/$(PKG).exe
WININSTALLER_SRC=installer.iss


# personal www paths
WWW=/var/www/dev/rasm/keepnote


#=============================================================================
# linux build

.PHONY: all sdist rpm deb ebuild clean cq test help share \
	winebuild wineinstaller winclean contribs \
	pypi upload upload-test upload-contrib

all: $(UPLOAD_FILES)

# source distribution *.tar.gz
sdist: $(SDIST)
$(SDIST):
	$(PYTHON) setup.py sdist

# RPM binary package
rpm: $(RPM)
$(RPM):
	$(PYTHON) setup.py bdist --format=rpm

# Debian package
deb: $(DEB)
$(DEB): $(SDIST)
	pkg/deb/make-deb.sh $(VERSION)
	mv pkg/deb/$(DEB_FILE) $(DEB)

# Gentoo package
ebuild: $(EBUILD)
$(EBUILD):
	cp pkg/ebuild/$(PKG)-template.ebuild $(EBUILD)

clean:
	rm -rf $(TMP_FILES) $(UPLOAD_FILES) $(WINDIR) $(WININSTALLER_SRC)

cq:
	pep8 $(CODEQUALITY_FILES) | grep -v 'tarfile\|sqlitedict' || true
	pyflakes $(CODEQUALITY_FILES) | grep -v 'tarfile\|sqlitedict' || true

test:
	nosetests -sv tests/*.py

# show makefile actions
help:
	grep '^[^$$][^\w=]*:[^=]*$$' Makefile | sed 's/:.*//'

#=============================================================================
# icons

share:
	mkdir -p share/icons/gnome/16x16/
	cp -r -L /usr/share/icons/gnome/16x16/mimetypes share/icons/gnome/16x16/
	mkdir -p share/icons/gnome/16x16/actions
	cp -L /usr/share/icons/gnome/16x16/actions/gtk-execute.png share/icons/gnome/16x16/actions

#=============================================================================
# wine build

winebuild: $(WINEXE)
$(WINEXE):
	pkg/win/build.sh


wineinstaller: $(WININSTALLER)
$(WININSTALLER): $(WINEXE) $(WININSTALLER_SRC)
	./wine.sh iscc $(WININSTALLER_SRC)

$(WININSTALLER_SRC):
	$(PYTHON) pkg/win/make-win-installer-src.py \
		pkg/win/installer-template.iss > $(WININSTALLER_SRC)

winclean:
	rm -rf $(WININSTALLER) $(WININSTALLER_SRC) $(WINDIR)


#=============================================================================
# contrib

contribs:
	make -C contrib

#=============================================================================
# upload

pypi:
	$(PYTHON) setup.py register

upload: $(UPLOAD_FILES)
	cp $(UPLOAD_FILES) $(WWW)/download
	tar zxv -C $(WWW)/download \
	    -f $(WWW)/download/$(SDIST_FILE)

upload-test: $(UPLOAD_FILES)
	cp $(UPLOAD_FILES) $(WWW)/download-test

upload-contrib:
	make -C contrib upload

