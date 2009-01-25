#
# Makefile for KeepNote
#
# I keep common building task here
#

PKG=keepnote
VERSION=0.5

# release files
INSTALLER=dist/$(PKG)-$(VERSION).exe

SDISTFILE=$(PKG)-$(VERSION).tar.gz
RPMFILE=$(PKG)-$(VERSION)-1.noarch.rpm
EBUILDFILE=$(PKG)-$(VERSION).ebuild
DEBFILE=$(PKG)_$(VERSION)-1_all.deb

SDIST=dist/$(SDISTFILE)
RPM=dist/$(RPMFILE)
DEB=dist/$(DEBFILE)
EBUILD=dist/$(EBUILDFILE)


UPLOAD_FILES=$(SDIST) $(RPM) $(DEB) $(EBUILD) $(INSTALLER)

# personal www paths
LINUX_WWW=/var/www/dev/rasm/keepnote
WIN_WWW=/z/mnt/big/www/dev/rasm/keepnote


#=============================================================================
# windows build

winupload:
	cp $(INSTALLER) $(WIN_WWW)/download

winbuild:
	python setup.py py2exe
	iscc installer.iss

winebuild: dist/$(PKG)-$(VERSION).win/$(PKG).exe

dist/$(PKG)-$(VERSION).win/$(PKG).exe:
	./wine.sh python setup.py py2exe
	python fix_pe.py


wineinstaller: $(INSTALLER)

$(INSTALLER): dist/$(PKG)-$(VERSION).win/$(PKG).exe
	./wine.sh iscc installer.iss

winclean:
	rm -rf dist
	rm -f $(INSTALLER)

#=============================================================================
# linux build

all: $(UPLOAD_FILES)

sdist: $(SDIST)
$(SDIST):
	python setup.py sdist

rpm: $(RPM)
$(RPM):
	python setup.py bdist --format=rpm

deb: $(DEB)
$(DEB): $(SDIST)
	pkg/deb/make-deb.sh $(VERSION)
	mv pkg/deb/$(DEBFILE) $(DEB)

ebuild: $(EBUILD)
$(EBUILD):
	cp pkg/ebuild/$(PKG)-template.ebuild $(EBUILD)


clean:
	rm -rf $(UPLOAD_FILES)

#=============================================================================
# linux upload

pypi:
	python setup.py register


upload: $(UPLOAD_FILES)
	cp $(UPLOAD_FILES) $(LINUX_WWW)/download
	tar zxv -C $(LINUX_WWW)/download \
	    -f $(LINUX_WWW)/download/$(SDISTFILE)

