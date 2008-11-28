#
# Makefile for TakeNote
#
# I keep common building task here
#

PKG=takenote
VERSION=0.4.5


INSTALLER=Output/$(PKG)-$(VERSION).exe
SDIST=dist/$(PKG)-$(VERSION).tar.gz
RPM=dist/$(PKG)-$(VERSION)-1.noarch.rpm

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

pypi:
	python setup.py register


upload: $(SDIST) $(RPM)
	cp $(SDIST) $(RPM) $(LINUX_WWW)/download
	tar zxv -C $(LINUX_WWW)/download \
	    -f $(LINUX_WWW)/download/$(PKG)-$(VERSION).tar.gz

