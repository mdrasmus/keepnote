"""

   Fix the image size of an EXE (PE image)
   This is needed due to a bug in WINE during cross-compiling

"""


from keepnote import PROGRAM_VERSION_TEXT
import pefile

exe_file = 'dist/keepnote-%s.win/keepnote.exe' % PROGRAM_VERSION_TEXT


# read PE file
pe =  pefile.PE(exe_file)

print "old OPTIONAL_HEADER.SizeOfImage =", hex(pe.OPTIONAL_HEADER.SizeOfImage)

# recalculate image size
size = pe.sections[-1].VirtualAddress + pe.sections[-1].Misc_VirtualSize
pe.OPTIONAL_HEADER.SizeOfImage = size

print "new OPTIONAL_HEADER.SizeOfImage =", hex(size)


# write new PE file
pe.write(exe_file)

