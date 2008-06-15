#!/usr/bin/env python
# 
# setup for SUMMON package
#
# use the following to install summon:
#   python setup.py install
#

import os, sys, shutil
from distutils.core import setup, Extension

try:
    import py2exe
except ImportError:
    pass


TAKENOTE_VERSION = '0.4'

# get images
image_dir = "takenote/images"
image_files = [os.path.join(image_dir, x) 
               for x in os.listdir("takenote/images")]


if "py2exe" in sys.argv:
    data_files = [
        ('images', image_files),
        
        ('rc', ['takenote/rc/takenote.glade'])
    ]
else:
    data_files = []


setup(
    name='takenote',
    version=TAKENOTE_VERSION,
    description='A cross-platform note taking application',
    long_description = """
        TakeNote is a cross-platform note taking application.  Its features 
        include:
        
        - rich text editing
        - hierarchical organization for notes
        - inline images
        - integrated screenshot
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
    
    packages=['takenote', 'takenote.gui'],
    scripts=['bin/takenote'],
    data_files=data_files,
    
    package_data={'takenote': image_files + ["rc/takenote.glade"]},
    
    windows=[{
        'script': 'bin/takenote',
        'icon_resources': [(1, 'takenote/images/note.ico')],
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
