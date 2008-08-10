#
# Makefile for TakeNote
#
# I keep common building task here
#

PKG=takenote
VERSION=0.4.1
INSTALLER=Output/$(PKG)-$(VERSION).exe

SCP=scp

winbuild: $(INSTALLER)

$(INSTALLER):
	python setup.py py2exe
	iscc installer.iss

winupload: $(INSTALLER)
	cp $(INSTALLER) /z/mnt/big/www/dev/rasm/takenote/download/


winclean:
	rm -rf dist
	rm -f $(INSTALLER)

