#!/bin/sh


LANGS="fr_FR.UTF8 tr_TR.UTF8"

# extract new strings
make -f Makefile.gettext extract
echo -e "\n\n\n"

# update and make each file
for L in $LANGS; do
    echo "making $LANG..."
    make -f Makefile.gettext update LANG=$L
    make -f Makefile.gettext make LANG=$L

    FUZZY=$(egrep "^#.*fuzzy" gettext/$L.po | wc -l)
    if [ $FUZZY -gt 0 ]; then
	echo "warning: $FUZZY strings need checking (fuzzy match)"
    fi

    echo -e "\n"
done

