#!/usr/bin/env python

import sys
from StringIO import StringIO
import xml.etree.ElementTree as ET

from keepnote import plist



elm = plist.load(StringIO("""<dict><key>aaa</key><integer>444</integer>
 <key>11</key><true/></dict>"""))
print elm, type(elm), elm.keys()

plist.dump(elm)


data = {"version": [1, 0, 3],
     "kind": "nice",
     "measure": 3.03,
     "use_feature": True
     }

#print
#print "1: "
#plist.dump(data)

print
print
print "2: "
s = plist.dumps(data, indent=4)
print s

print plist.loads(s)


#print plist.ET.XML("<?xml version='1.0'?>\n<dict><key>aaa</key><integer>444</integer>")

print 
print "load_etree"
s = plist.dumps(data, indent=4)
x = ET.fromstring(s)
print plist.load_etree(x)

print 
print "dump_etree"
e = ET.ElementTree(plist.dump_etree(data))
e.write(sys.stdout)


