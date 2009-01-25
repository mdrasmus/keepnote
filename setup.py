#!/usr/bin/env python
# 
# setup for KeepNote
#
# use the following command to install KeepNote:
#   python setup.py install
#
#=============================================================================


# python and distutils imports
import os, sys, shutil
#from ez_setup import use_setuptools
#use_setuptools()
#from setuptools import setup, find_packages
from distutils.core import setup

# py2exe module (if building on windows)
try:
    import py2exe
except ImportError:
    pass

#=============================================================================
# constants

import keepnote
KEEPNOTE_VERSION = keepnote.PROGRAM_VERSION_TEXT


#=============================================================================
# helper functions

# get extensions
def get_extension_files():
    efiles = {}
    def walk(path, path2):
        for f in os.listdir(path):
            filename = os.path.join(path, f)
            filename2 = os.path.join(path2, f)
            if filename.endswith(".pyc"):
                # ignore .pyc files
                continue
            elif os.path.isdir(filename):
                # recurse directories
                
                walk(filename, filename2)
            else:
                # record all other files
                efiles.setdefault(path2, []).append(filename)
    walk("keepnote/extensions", "extensions")
    return efiles


def get_image_files(image_dir):
    return [os.path.join(image_dir, x)
            for x in os.listdir(image_dir)]

def remove_package_dir(filename):
    i = filename.index("/")
    return filename[i+1:]


#=============================================================================
# resource files/data

# get resources
resource_files = ["keepnote/rc/keepnote.glade"]
image_files = get_image_files("keepnote/images")
efiles = get_extension_files()
freedesktop_files = [
    # application icon
    ("share/icons/hicolor/48x48/apps",
     ["desktop/keepnote.png"]),

    # desktop menu entry
    ("share/applications",
     ["desktop/keepnote.desktop"])]


# get data files
if "py2exe" in sys.argv:
    data_files = [
        ('images', image_files),
        ('rc', resource_files)
    ] + efiles.items()
    package_data = {}
    
else:
    data_files = freedesktop_files
    package_data = {'keepnote':
                    map(remove_package_dir,
                        image_files +
                        resource_files)
                    }
    for v in efiles.values():
        package_data['keepnote'].extend(map(remove_package_dir, v))




#=============================================================================
# setup

setup(
    name='keepnote',
    version=KEEPNOTE_VERSION,
    description='A cross-platform note taking application',
    long_description = """
        KeepNote is a cross-platform note taking application.  Its features 
        include:
        
        - rich text editing
        
          - bullet points
          - fonts/colors
          - hyperlinks
          - inline images
          
        - hierarchical organization for notes
        - full text search
        - integrated screenshot
        - spell checking (via gtkspell)
        - backup and restore
    """,
    author='Matt Rasmussen',
    author_email='rasmus@mit.edu',
    url='http://rasm.ods.org/keepnote/',
    download_url='http://rasm.ods.org/keepnote/download/keepnote-%s.tar.gz' % KEEPNOTE_VERSION,
    
    classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Environment :: Win32 (MS Windows)',
          'Environment :: X11 Applications',
          'Intended Audience :: Developers',
          'Intended Audience :: Education',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GNU General Public License (GPL)',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          ],
    license="GPL",
    
    packages=['keepnote',
              'keepnote.gui',
              'keepnote.gui.richtext',
              'keepnote.compat'],
    scripts=['bin/keepnote'],
    data_files=data_files,
    package_data=package_data,
    
    windows=[{
        'script': 'bin/keepnote',
        'icon_resources': [(1, 'keepnote/images/keepnote.ico')],
        }],
    options = {
        'py2exe' : {
            'packages': 'encodings',
            'includes': 'cairo,pango,pangocairo,atk,gobject',
            'dist_dir': 'dist/keepnote-%s.win' % KEEPNOTE_VERSION
        },
        #'sdist': {
        #    'formats': 'zip',
        #}
    }
    )


# execute post-build script
if "py2exe" in sys.argv:
    execfile("post_py2exe.py")
