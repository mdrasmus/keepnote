#!/bin/sh


#LANGS="fr_FR.UTF8 tr_TR.UTF8 es_ES.UTF8"
LANGS=$(ls gettext/*.po | (while read x; do basename $x | sed 's/.po//'; done))

# extract new strings
make -f Makefile.gettext extract
echo -e "\n\n\n"

# update and make each file
for L in $LANGS; do
    echo "making $L..."
    make -f Makefile.gettext update LANG=$L
    make -f Makefile.gettext make LANG=$L

    FUZZY=$(egrep "^#.*fuzzy" gettext/$L.po | wc -l)
    if [ $FUZZY -gt 0 ]; then
	echo "warning: $FUZZY strings have a fuzzy match"
    fi

    EMPTY=$(egrep 'msgstr ""' gettext/$L.po | wc -l)
    if [ $EMPTY -gt 0 ]; then
	echo "warning: $EMPTY strings are empty"
    fi

    DEL=$(egrep '^#~ msgid' gettext/$L.po | wc -l)
    if [ $DEL -gt 0 ]; then
	echo "warning: $DEL deleted strings"
    fi

    echo; echo
done

# remove ~ files
rm gettext/*~

