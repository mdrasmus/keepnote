Translations for KeepNote
-------------------------

KeepNote now supports translations through the gettext system.  If you would
like to create a translation for KeepNote, please let me know,
rasmus[at]mit[dot]edu.  Below are the basic steps for beginning or modifying
a translation for KeepNote.

1. File layout
--------------

Makefile.gettext		     Makefile with gettext commands
gettext/messages.pot                 all strings extracted from KeepNote source
gettext/$LANG.po                     language-specific translations
locale/$LANG/LC_MESSAGES/keepnote.mo compiled translations for KeepNote


2. Extract all strings from KeepNote source
-------------------------------------------

All common commands for manipulating translations are supported through the
KeepNote Makefile.  If strings are changed in the source code, they need to
be extracted into the 'gettext/messages.pot' file by using the following
command:

    make -f Makefile.gettext extract


3. Create a new translation
---------------------------

If your language is not already present (should be 'gettext/$LANG.po'), then
use this command to create a blank translation file:

    make -f Makefile.gettext new LANG=de_DE.UTF8

In this example, a new translation for de_DE.UTF8 (German) is created.  You
can now edit the file 'gettext/de_DE.UTF8.po'


4. Updating an existing translation with new extracted strings
--------------------------------------------------------------

If strings within the source code have been changed, they must be extracted
again (see step 2) and merged into the existing translations within
'gettext/$LANG.po'.  If you were working on the German translation the 
command is:

    make -f Makefile.gettext update LANG=de_DE.UTF8


5. Compiling translations
-------------------------

Once translations are written in 'gettext/$LANG.po' they must be compiled into
a file named 'locale/$LANG/LC_MESSAGES/keepnote.mo'.  Use this command,

    make -f Makefile.gettext make LANG=de_DE.UTF8


6. Testing/Using a translation
------------------------------

To test or use a translation make sure that the LANG environment variable
is set to the translation you would like to use, prior to running KeepNote.
For example, to run KeepNote with German translations use:

    LANG=de_DE.UTF8 bin/keepnote


7. Submitting your translation for inclusion in the KeepNote distribution
-------------------------------------------------------------------------

If you would like your translation to be a part of the official KeepNote
distribution please send your *.po file to rasmus[at]mit[edu].  If you wish
I can add your name to the translation credits.

