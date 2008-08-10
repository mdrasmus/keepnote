#
# Makefile for TakeNote
#
# I keep common building task here
#

PKG=takenote
VERSION=0.4.1

winbuild:
	rm -rf dist
	python setup.py py2exe
	iscc installer.iss
	scp Output/$(PKG)-$(VERSION).exe raz@viktor.ods.org:/var/www/dev/rasm/takenote/download/


