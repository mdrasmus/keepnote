#!/bin/sh

echo "set PATH=%PATH%;C:\\GTK\\bin;C:\\Python25;C:\\Program Files\\Inno Setup 5" > wine.bat
echo $* >> wine.bat
echo "pause" >> wine.bat

#WINEDLLOVERRIDES="imagehlp,msimg=n" wine start wine.bat
WINEDLLOVERRIDES="imagehlp,msimg=n" wineconsole --backend=curses wine.bat

