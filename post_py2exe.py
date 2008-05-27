
import os, sys, shutil

from pywin import find_path


def include(src, dest, exclude=[]):
    if not os.path.exists(dest):
        print "copying %s..." % dest
        
        # ensure base exists
        base = os.path.split(dest)[0]
        if not os.path.exists(base):
            os.makedirs(base)
        
        shutil.copytree(src, dest)

def prune(path):
    if os.path.exists(path):
        print "pruning %s..." % path
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

        
include(find_path("GTK/lib/gtk-2.0/2.10.0/engines"), "dist/lib/gtk-2.0/2.10.0/engines")
include(find_path("GTK/lib/gtk-2.0/2.10.0/loaders"), "dist/lib/gtk-2.0/2.10.0/loaders")
include(find_path("GTK/lib/pango"), "dist/lib/pango")
include(find_path("GTK/etc"), "dist/etc")

#include(find_path("GTK/share"), "dist/share")
include(find_path("GTK/share/applications"), "dist/share/applications")
include(find_path("GTK/share/gettext"), "dist/share/gettext")
include(find_path("GTK/share/glade3"), "dist/share/glade3")
include(find_path("GTK/share/glib-2.0"), "dist/share/glib-2.0")
include(find_path("GTK/share/gtk-2.0"), "dist/share/gtk-2.0")
include(find_path("GTK/share/gtkthemeselector"), "dist/share/gtkthemeselector")
include(find_path("GTK/share/icons/hicolor/16x16/stock"), "dist/share/icons/hicolor/16x16/stock")
include(find_path("GTK/share/locale/en@quot"), "dist/share/locale/en@quot")
include(find_path("GTK/share/locale/en@boldquot"), "dist/share/locale/en@boldquot")
include(find_path("GTK/share/locale/en_CA"), "dist/share/locale/en_CA")
include(find_path("GTK/share/locale/en_GB"), "dist/share/locale/en_GB")
include(find_path("GTK/share/themes"), "dist/share/themes")
include(find_path("GTK/share/xml"), "dist/share/xml")

#prune("dist/share/doc")
#prune("dist/share/gtk-doc")
#for name in os.listdir("dist/share/locale"):
#    if "en" not in name:
#        prune("dist/share/locale/%s" % name)

