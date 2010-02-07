
WWW=/var/www/dev/rasm/keepnote

UPLOAD_FILES=import_notecase.kne

import_notecase.kne: import_notecase/__init__.py
	rm -f import_notecase.kne
	zip -r import_notecase.kne import_notecase


upload: $(UPLOAD_FILES)
	mkdir -p $(WWW)/download/extensions/
	cp $(UPLOAD_FILES) $(WWW)/download/extensions/

