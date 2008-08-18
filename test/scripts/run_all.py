#!/usr/bin/env python


import sys
import unittest

sys.path.append("../..")
sys.path.append(".")

import test_richtext_html

# run HtmlBuffer tests
#unittest.main()
suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_richtext_html.TestCaseHtmlBuffer)
unittest.TextTestRunner(verbosity=2).run(suite)


