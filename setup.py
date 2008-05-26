#!/usr/bin/env python
# 
# setup for SUMMON package
#
# use the following to install summon:
#   python setup.py install
#

import os, sys, shutil
from distutils.core import setup, Extension
import py2exe

TAKENOTE_VERSION = '1.0'

# get images
image_dir = "images"
image_files = [os.path.join(image_dir, x) 
               for x in os.listdir("images")]

setup(
    name='takenote',
    version=TAKENOTE_VERSION,
    description='A cross-platform note taking application',
    long_description = """
        TakeNote is a cross-platform note taking application.  It's features 
        include:
        
        - rich text editing
        - hierarchical organization for notes
        - inline images
        - integrated screenshot imports
        - spell checking (via gtkspell)
    """,
    author='Matt Rasmussen',
    author_email='rasmus@mit.edu',
    url='http://people.csail.mit.edu/rasmus/takenote/',
    download_url='http://compbio.mit.edu/pub/takenote/takenote-%s.tar.gz' % TAKENOTE_VERSION,
    
    classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Environment :: Win32 (MS Windows)',
          'Environment :: X11 Applications',
          'Intended Audience :: Developers',
          'Intended Audience :: Education',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          ],
    
    #package_dir = {'': 'lib'},
    packages=['takenote'],
    #py_modules=['summon_config'],
    scripts=['bin/takenote'],
    data_files=[
        ('images', image_files),
        ('rc', ['rc/app_config.glade'])
    ],
    
    windows=[{
        'script': 'bin/takenote',
        'icon_resources': [(1, 'images/note.ico')],
        }],
    options = {
        'py2exe' : {
            'packages':'encodings',
            'includes': 'cairo,pango,pangocairo,atk,gobject',
        },
        'sdist': {
            'formats': 'zip',
        }
    }
    )


# execute post-build script
if "py2exe" in sys.argv:
    execfile("post_py2exe.py")
