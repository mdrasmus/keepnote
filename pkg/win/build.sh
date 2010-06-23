#!/bin/sh


if [ "x$1" = "xtest" ]; then
    ./wine-debug.sh python setup.py py2exe
    ./wine-debug.sh python setup.py py2exe

else
    ./wine.sh python setup.py py2exe
    ./wine.sh python setup.py py2exe
fi

python pkg/win/fix_pe.py



