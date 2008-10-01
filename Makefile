#
# Makefile for TakeNote
#
# I keep common building task here
#

PKG=takenote
VERSION=0.4.3


INSTALLER=Output/$(PKG)-$(VERSION).exe
SDIST=dist/$(PKG)-$(VERSION).tar.gz

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

sdist:
	python setup.py sdist

pypi:
	python setup.py register


upload: $(SDIST)
	cp $(SDIST) $(LINUX_WWW)/download
	tar zxv -C $(LINUX_WWW)/download \
	    -f $(LINUX_WWW)/download/$(PKG)-$(VERSION).tar.gz

