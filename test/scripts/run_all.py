#!/usr/bin/env python


import sys
import unittest

sys.path.append("../..")
sys.path.append(".")

import test_richtext_html as html

# run HtmlBuffer tests
#unittest.main()

all = (len(sys.argv) == 1)

if all or "html" in sys.argv:
    unittest.TextTestRunner(verbosity=2).run(html.richtextbuffer_suite)
    unittest.TextTestRunner(verbosity=2).run(html.htmlbuffer_suite)



