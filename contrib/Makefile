
UPLOAD_FILES=import_notecase.kne

WWW=/var/www/dev/rasm/keepnote

all: $(UPLOAD_FILES)


# notecase importer
import_notecase.kne: import_notecase/__init__.py
	rm -f import_notecase.kne
	zip -r import_notecase.kne import_notecase

#=============================================================================
# uploading

upload: $(UPLOAD_FILES)
	mkdir -p $(WWW)/download/extensions/
	cp $(UPLOAD_FILES) $(WWW)/download/extensions/

