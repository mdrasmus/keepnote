
import os, sys, shutil

from pywin import find_path

import keepnote

dest = "dist/keepnote-%s.win/" % keepnote.PROGRAM_VERSION_TEXT



def include(src, dest, exclude=[]):
    if not os.path.exists(dest):
        print "copying %s..." % dest
        
        # ensure base exists
        base = os.path.split(dest)[0]
        if not os.path.exists(base):
            os.makedirs(base)

        if os.path.isfile(src):
            shutil.copyfile(src, dest)
        else:
            shutil.copytree(src, dest)

def prune(path):
    if os.path.exists(path):
        print "pruning %s..." % path
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


# needed for win32ui
include(find_path("windows/system32/mfc71.dll"), dest+"mfc71.dll")

# needed for sqlite on Windows 7
#include("pkg/win/sqlite3.dll", dest+"sqlite3.dll")
# doesn't work yet, breaks search

        
include(find_path("GTK/lib/gtk-2.0/2.10.0/engines"), dest+"lib/gtk-2.0/2.10.0/engines")
include(find_path("GTK/lib/gtk-2.0/2.10.0/loaders"), dest+"lib/gtk-2.0/2.10.0/loaders")
include(find_path("GTK/lib/pango"), dest+"lib/pango")

# needed for jpeg
include(find_path("GTK/bin/jpeg62.dll"), dest+"jpeg62.dll")

include(find_path("GTK/etc"), dest+"etc")


# OLD paths no long included
#include(find_path("GTK/share/applications"), dest+"share/applications")
#include(find_path("GTK/share/gettext"), dest+"share/gettext")
#include(find_path("GTK/share/glib-2.0"), dest+"share/glib-2.0")
#include(find_path("GTK/share/gtk-2.0"), dest+"share/gtk-2.0")
#include(find_path("GTK/share/icons/hicolor/16x16/stock"), dest+"share/icons/hicolor/16x16/stock")


include(find_path("GTK/share/glade3"), dest+"share/glade3")
include(find_path("GTK/share/gtkthemeselector"), dest+"share/gtkthemeselector")
include("share/icons/gnome/16x16/actions", dest+"share/icons/hicolor/16x16/actions")
include("share/icons/gnome/16x16/mimetypes", dest+"share/icons/hicolor/16x16/mimetypes")
include("pkg/win/index.theme", dest+"share/icons/hicolor/index.theme")
include(find_path("GTK/share/locale/en@quot"), dest+"share/locale/en@quot")
include(find_path("GTK/share/locale/en@boldquot"), dest+"share/locale/en@boldquot")
include(find_path("GTK/share/locale/en_CA"), dest+"share/locale/en_CA")
include(find_path("GTK/share/locale/en_GB"), dest+"share/locale/en_GB")
include(find_path("GTK/share/themes"), dest+"share/themes")
include(find_path("GTK/share/xml"), dest+"share/xml")

# make sure accels can be changed
out = open(dest+"etc/gtk-2.0/gtkrc", "a")

# allow customization of shortcuts
out.write("gtk-can-change-accels = 1\n")

# suppress bell sound
out.write("gtk-error-bell = 0\n")

out.close()

