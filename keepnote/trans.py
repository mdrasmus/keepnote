"""
    KeepNote
    Translation module
"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@mit.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#

import os
import gettext
import locale

import keepnote

locale.setlocale(locale.LC_ALL, "")


# global translation object
_translation = None
_lang = None


def set_lang(lang=None, localedir=None):
    """Set the locale"""

    global _translation, _lang

    
    # setup language preference order
    languages = []
    
    # default language from environment
    deflang, defencoding = locale.getdefaultlocale()
    if deflang:
        languages = [deflang+"."+defencoding] + languages

    # specified language
    if lang:
        languages = [lang] + languages

    # initialize gettext
    if localedir is None:
        localedir = keepnote.get_locale_dir()
    gettext.bindtextdomain(keepnote.GETTEXT_DOMAIN, localedir)
    gettext.textdomain(keepnote.GETTEXT_DOMAIN)

    # search for language file
    langfile = gettext.find(keepnote.GETTEXT_DOMAIN, localedir, languages)
    

    # setup language translations
    if langfile:
        _translation = gettext.GNUTranslations(open(langfile))
        _lang = os.path.basename(os.path.dirname(
                os.path.dirname(langfile)))
        
    else:
        _translation = gettext.NullTranslations()
        _lang = ""


def get_lang():
    return _lang


def translate(message):
    """Translate a string into the current language"""
    return _translation.gettext(message)


def get_langs(localedir=None):
    """Return available languages"""
    if localedir is None:
        localedir = keepnote.get_locale_dir()

    return os.listdir(localedir)




'''
#Translation stuff

#Get the local directory since we are not installing anything
self.local_path = os.path.realpath(os.path.dirname(sys.argv[0]))
# Init the list of languages to support
langs = []
#Check the default locale
lc, encoding = locale.getdefaultlocale()
if (lc):
	#If we have a default, it's the first in the list
	langs = [lc]
# Now lets get all of the supported languages on the system
language = os.environ.get('LANGUAGE', None)
if (language):
	"""langage comes back something like en_CA:en_US:en_GB:en
	on linuxy systems, on Win32 it's nothing, so we need to
	split it up into a list"""
	langs += language.split(":")
"""Now add on to the back of the list the translations that we
know that we have, our defaults"""
langs += ["en_CA", "en_US"]

"""Now langs is a list of all of the languages that we are going
to try to use.  First we check the default, then what the system
told us, and finally the 'known' list"""

gettext.bindtextdomain(APP_NAME, self.local_path)
gettext.textdomain(APP_NAME)
# Get the language to use
self.lang = gettext.translation(APP_NAME, self.local_path
	, languages=langs, fallback = True)
"""Install the language, map _() (which we marked our
strings to translate with) to self.lang.gettext() which will
translate them."""
_ = self.lang.gettext
'''
