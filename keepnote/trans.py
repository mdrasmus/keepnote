"""
    KeepNote
    Translation module
"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@alum.mit.edu>
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
import ctypes
from ctypes import cdll

# try to import windows lib
try:
    msvcrt = cdll.msvcrt
    msvcrt._putenv.argtypes = [ctypes.c_char_p]
    _windows = True
except:
    _windows = False


# global translation object
GETTEXT_DOMAIN = 'keepnote'
_locale_dir = u"."
_translation = None
_lang = None


try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    # environment variable LANG may specify an unsupported locale
    pass


# we must not let windows environment variables deallocate
# thus we keep a global list of pointers
#_win_env = []

def set_env(key, val):
    """Cross-platform environment setting"""
    
    if _windows:
        # ignore settings that don't change
        if os.environ.get(key, "") == val:
            return

        setstr = u"%s=%s" % (key, val)
        #setstr = x.encode(locale.getpreferredencoding())
        msvcrt._putenv(setstr)

        #win32api.SetEnvironmentVariable(key, val)
        #ctypes.windll.kernel32.SetEnvironmentVariableA(key, val)

        # NOTE: we only need to change the python copy of the environment
        # The data member is only available if we are on windows
        os.environ.data[key] = val
    else:
        os.environ[key] = val


def set_local_dir(dirname):
    """Set the locale directory"""
    global _locale_dir
    _locale_dir = dirname


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
        localedir = _locale_dir
    gettext.bindtextdomain(GETTEXT_DOMAIN, localedir)
    gettext.textdomain(GETTEXT_DOMAIN)

    # search for language file
    langfile = gettext.find(GETTEXT_DOMAIN, localedir, languages)

    # setup language translations
    if langfile:
        _lang = os.path.basename(os.path.dirname(
                os.path.dirname(langfile)))
        set_env("LANG", _lang)
        set_env("LANGUAGE", _lang)
        _translation = gettext.GNUTranslations(open(langfile, "rb"))
    else:
        _lang = ""
        set_env("LANG", _lang)
        set_env("LANGUAGE", _lang)
        _translation = gettext.NullTranslations()

    # install "_" into python builtins
    _translation.install()


def get_lang():
    return _lang


def translate(message):
    """Translate a string into the current language"""
    if _translation is None:
        return message
    return _translation.gettext(message)


def get_langs(localedir=None):
    """Return available languages"""

    if localedir is None:
        localedir = _locale_dir

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
