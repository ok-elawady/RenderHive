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

    def test_all_colors_accessed_in_window_and_page_exist_in_theme(self):
        import re
        import sys
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from ui.qt_theme import COLORS

        for file_path in (VALIDATION_PAGE, WINDOW_PATH):
            with open(file_path, "r", encoding="utf-8") as handle:
                source = handle.read()
            keys = re.findall(r'COLORS\[["\'](\w+)["\']\]', source)
            for k in keys:
                self.assertIn(k, COLORS, "Key '{}' accessed in {} not in COLORS".format(k, file_path))


if __name__ == "__main__":
    unittest.main()
