#!/usr/bin/env python

from StringIO import StringIO
import unittest

from keepnote import plist


class PListTest(unittest.TestCase):
    def test_read_write_file(self):
        data = {
            'aaa': 444,
            '11': True,
        }
        plist_xml = ("<dict><key>aaa</key><integer>444</integer>"
                     "<key>11</key><true/></dict>")

        elm = plist.load(StringIO(plist_xml))
        self.assertEqual(elm, data)

        out = StringIO()
        plist.dump(elm, out)
        self.assertEqual(out.getvalue(), plist_xml)

    def test_read_write_string(self):
        data = {
            "version": [1, 0, 3],
            "kind": "nice",
            "measure": 3.03,
            "use_feature": True
        }
        plist_xml = """\
<dict>
    <key>kind</key><string>nice</string>
    <key>version</key><array>
        <integer>1</integer>
        <integer>0</integer>
        <integer>3</integer>
    </array>
    <key>use_feature</key><true/>
    <key>measure</key><real>3.030000</real>
</dict>
"""
        elm = plist.loads(plist_xml)
        self.assertEqual(elm, data)

        text = plist.dumps(data, indent=4)
        self.assertEqual(text, plist_xml)
