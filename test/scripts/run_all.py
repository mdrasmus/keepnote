#!/usr/bin/env python


import sys
import unittest

sys.path.append("../..")
sys.path.append(".")

import test_richtext_html as html
import test_notebook_changes

# run HtmlBuffer tests
#unittest.main()

all = (len(sys.argv) == 1)

if all or "html" in sys.argv:
    unittest.TextTestRunner(verbosity=2).run(html.richtextbuffer_suite)
    unittest.TextTestRunner(verbosity=2).run(html.htmlbuffer_suite)

if all or "notebook" in sys.argv:
    unittest.TextTestRunner(verbosity=2).run(
        test_notebook_changes.notebook_changes_suite)
    

