#!/bin/sh

./wine.sh python setup.py py2exe
./wine.sh python setup.py py2exe
python pkg/win/fix_pe.py


