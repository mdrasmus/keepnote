KeepNote Install Instructions
=============================

## Windows Install

There is a binary installer for Windows available on the KeepNote website.
It is the recommended way to install KeepNote for Windows.


## Linux Install

###  Debian (or similar distribution such as Ubuntu)

If you run the Debian distribution, there is a *.deb package for
KeepNote available from the website.  Before installing KeepNote,
ensure you have installed the required libraries with this command:

```sh
apt-get install python python-gtk2 python-glade2 libgtk2.0-dev
```

You most likely need root permissions for this command (see `sudo`).
There are also optional libraries (for enabling spell checking, etc)

```sh
apt-get install python-gnome2-extras
```

Once you download the package `keepnote_X.Y.Z-1_all.deb` you can
install it with the command:

```sh
dpkg -i keepnote_X.Y.Z-1_all.deb
```

### Other Linux distributions:

KeepNote requires these third-party libraries installed:

- required: python python-gtk2 python-glade2 libgtk2.0-dev
- optional: python-gnome2-extras

Depending on the distribution the libraries may be named differently
(Debian names given).

Once third-party libraries are installed, you can download and extract
the `*.tar`.gz file using the command (if you haven't already done so):

```sh
tar zxvf keepnote-X.Y.Z.tar.gz
```

where X.Y.Z is the version of KeepNote you have downloaded.  One of
the easiest ways to run keepnote, is directly from its source
directory using the command:

```sh
YOUR_DOWNLOAD_PATH/keepnote-X.Y.Z/bin/keepnote
```

or you can install with python distutils:

```
python setup.py install
```

To install KeepNote as a non-root user you can do:

```sh
python setup.py install --prefix=YOUR_INSTALL_LOCATION
```

Lastly, KeepNote can be install from [PyPI](https://pypi.python.org/pypi):

```sh
pip install keepnote
```

This will download and install KeepNote to your default path.


## Mac OS X Install

All third-party libraries for the Linux version of KeepNote are 
cross-platform and should also work for Mac OS X.  

 - python (http://www.python.org)
 - gtk (http://www.gtk.org)
 - pygtk (http://www.pygtk.org)

All of these libraries are also available through
[MacPorts](https://www.macports.org/) and [HomeBrew](brew.sh/) on Mac
OS X.  Once installed, KeepNote can be run directly from its source
directory.


For example, yo install dependencies with MacPorts use the following command:

```sh
sudo port install py27-gtk aspell aspell-dict-en sqlite3
```

You may need to add your own language's dictionary (aspell-dict-XX) for 
spell checking to work completely.


```sh
YOUR_DOWNLOAD_PATH/keepnote-X.Y.X/bin/keepnote
```
