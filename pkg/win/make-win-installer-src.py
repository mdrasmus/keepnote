
import sys
from keepnote import PROGRAM_NAME, PROGRAM_VERSION_TEXT


INSTALLER_SRC_TEMPLATE = sys.argv[1] #"pkg/win/installer-template.iss"


src = open(INSTALLER_SRC_TEMPLATE).read()

variables = {
    "${PKG}": PROGRAM_NAME,
    "${VERSION}": PROGRAM_VERSION_TEXT
    }

for old, new in variables.items():
    src = src.replace(old, new)

print src
