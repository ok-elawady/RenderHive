from __future__ import absolute_import

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATION_PAGE = os.path.join(ROOT, "ui", "pages", "validation_page.py")
WINDOW_PATH = os.path.join(ROOT, "ui", "qt_submitter_window.py")


class ValidationPageCallbackStaticTests(unittest.TestCase):
    def test_validation_page_uses_api_bridge_callbacks(self):
        with open(VALIDATION_PAGE, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn(
            "severity.currentIndexChanged.connect(self.api.refresh_validation_filters)",
            source,
        )
        self.assertIn(
            "category.currentIndexChanged.connect(self.api.refresh_validation_filters)",
            source,
        )
        self.assertIn("self.api.clear_validation_results", source)
        self.assertNotIn(
            "currentIndexChanged.connect(refresh_validation_filters)",
            source,
        )

    def test_api_bridge_exports_validation_callbacks(self):
        with open(WINDOW_PATH, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn(
            "api.refresh_validation_filters = refresh_validation_filters",
            source,
        )
        self.assertIn(
            "api.clear_validation_results = clear_validation_results",
            source,
        )


if __name__ == "__main__":
    unittest.main()
