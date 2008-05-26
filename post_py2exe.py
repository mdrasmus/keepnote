
import os, sys, shutil

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

        
include("c:/GTK/lib", "dist/lib")
include("c:/GTK/etc", "dist/etc")
include("c:/GTK/share", "dist/share")

prune("dist/share/doc")
prune("dist/share/gtk-doc")

for name in os.listdir("dist/share/locale"):
    if "en" not in name:
        prune("dist/share/locale/%s" % name)

