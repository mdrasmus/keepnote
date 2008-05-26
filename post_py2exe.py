
import os, sys, shutil

from pywin import find_path


def include(src, dest):
    if not os.path.exists(dest):
        print "copying %s..." % dest
        shutil.copytree(src, dest)

def prune(path):
    if os.path.exists(path):
        print "pruning %s..." % path
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

        
include(find_path("GTK/lib"), "dist/lib")
include(find_path("GTK/etc"), "dist/etc")
include(find_path("GTK/share"), "dist/share")

prune("dist/share/doc")
prune("dist/share/gtk-doc")

for name in os.listdir("dist/share/locale"):
    if "en" not in name:
        prune("dist/share/locale/%s" % name)

