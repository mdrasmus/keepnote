#
# Makefile for TakeNote
#
# I keep common building task here
#

PKG=takenote
VERSION=0.4.4

# release files
INSTALLER=Output/$(PKG)-$(VERSION).exe

SDISTFILE=$(PKG)-$(VERSION).tar.gz
RPMFILE=$(PKG)-$(VERSION)-1.noarch.rpm
EBUILDFILE=$(PKG)-$(VERSION).ebuild
DEBFILE=$(PKG)_$(VERSION)-1_all.deb

SDIST=dist/$(SDISTFILE)
RPM=dist/$(RPMFILE)
DEB=dist/$(DEBFILE)
EBUILD=dist/$(EBUILDFILE)


UPLOAD_FILES=$(SDIST) $(RPM) $(DEB) $(EBUILD)

# www paths
LINUX_WWW=/var/www/dev/rasm/takenote
WIN_WWW=/z/mnt/big/www/dev/rasm/takenote


#=============================================================================
# windows build
winbuild: $(INSTALLER)

winupload: $(INSTALLER)
	cp $(INSTALLER) $(WIN_WWW)/download

$(INSTALLER):
	python setup.py py2exe
	iscc installer.iss

winclean:
	rm -rf dist
	rm -f $(INSTALLER)

#=============================================================================
# linux build

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

#=============================================================================
# linux upload

pypi:
	python setup.py register


upload: $(UPLOAD_FILES)
	cp $(UPLOAD_FILES) $(LINUX_WWW)/download
	tar zxv -C $(LINUX_WWW)/download \
	    -f $(LINUX_WWW)/download/$(SDISTFILE)

