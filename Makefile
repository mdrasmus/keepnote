#
# Makefile for KeepNote
#
# common building tasks
#

PKG=keepnote
#VERSION=0.6
VERSION:=$(shell python -c 'import keepnote; print keepnote.PROGRAM_VERSION_TEXT')

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

TMP_FILES=MANIFEST

# windows related variables
WINDIR=dist/$(PKG)-$(VERSION).win
WINEXE=$(WINDIR)/$(PKG).exe
WININSTALLER_SRC=installer.iss


# personal www paths
WWW=/var/www/dev/rasm/keepnote


#=============================================================================
# linux build

all: $(UPLOAD_FILES)

# source distribution *.tar.gz
sdist: $(SDIST)
$(SDIST):
	python setup.py sdist

# RPM binary package
rpm: $(RPM)
$(RPM):
	python setup.py bdist --format=rpm

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


#=============================================================================
# wine build

winebuild: $(WINEXE)
$(WINEXE):
	pkg/win/build.sh


wineinstaller: $(WININSTALLER)
$(WININSTALLER): $(WINEXE) $(WININSTALLER_SRC)
	./wine.sh iscc $(WININSTALLER_SRC)

$(WININSTALLER_SRC):
	python pkg/win/make-win-installer-src.py \
		pkg/win/installer-template.iss > $(WININSTALLER_SRC)

winclean:
	rm -rf $(WININSTALLER) $(WININSTALLER_SRC) $(WINDIR)



#=============================================================================
# upload

pypi:
	python setup.py register


upload: $(UPLOAD_FILES)
	cp $(UPLOAD_FILES) $(WWW)/download
	tar zxv -C $(WWW)/download \
	    -f $(WWW)/download/$(SDIST_FILE)

upload-test: $(UPLOAD_FILES)
	cp $(UPLOAD_FILES) $(WWW)/download-test


