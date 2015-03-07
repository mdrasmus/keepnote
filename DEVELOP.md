Developing KeepNote
===================

## Linux/Mac OS X development.

Follow the install instructions to install all third-party libraries. Next,
a development enviroment can be setup by using the provided `Makefile`:

```sh
make dev
```

This should create a Python virtualenv directory `env` and install
several javascript related directories `node_modules` and
`bower_components`.

Tests can be run using:

```sh
make test
```

and code-quality can be checked using:

```sh
make cq
```


## Windows Build

Most people will just want to install KeepNote.  For basic
installation, see the [Windows Install instructions](INSTALL.md).  These
instructions are for developers who want to *build* the windows
installer.
  
First install these third party packages.  Versions that are known
to work are given below, but higher version are likely to also work.

```
python-2.5.1.msi
gtk-dev-2.12.9-win32-2.exe
pygtk-2.12.1-1.win32-py2.5.exe
pyobject-2.14.1-1.win32-py2.5.exe
pycario-1.4.12-1.win32-py2.5.exe
py2exe-0.6.6.win32-py2.5.exe
isetup-5.2.3.exe (Inno Setup)
pywin32-210.win32-py2.5.exe
```

**NOTE:** `pygtk-2.12.1-2.win32-py2.5.exe` (notice the -2) seems to
have a bug with `get_source_widget()`.

Once third-party packages are installed, execute in the KeepNote
source directory:

```sh
python setup.py py2exe
```

Use Inno to compile `installer.iss` into the final installer `*.exe`.

The `Makefile` includes a target `winebuild` to cross-compile the Windows
installer from Linux using [Wine](https://www.winehq.org/).

```sh
make winebuild
```
