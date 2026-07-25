from __future__ import absolute_import

import os
import unittest


class InfoTooltipPolicyTests(unittest.TestCase):
    def test_explanatory_widget_tooltips_only_live_on_info_icon(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ui_path = os.path.join(root, "ui", "qt_submitter_window.py")

        with open(ui_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        info_start = source.index("class InfoTipButton")
        info_end = source.index("class LabeledField")

        offset = 0
        for line_number, line in enumerate(source.splitlines(True), 1):
            stripped = line.strip()

            if ".setToolTip(" not in stripped:
                offset += len(line)
                continue

            if stripped.startswith("self.setToolTip("):
                self.assertTrue(
                    info_start <= offset < info_end,
                    "Unexpected widget tooltip at line {}: {}".format(
                        line_number,
                        stripped,
                    ),
                )
            else:
                self.assertTrue(
                    stripped.startswith("item.setToolTip(")
                    or stripped.startswith("pool_item.setToolTip("),
                    "Unexpected widget tooltip at line {}: {}".format(
                        line_number,
                        stripped,
                    ),
                )

            offset += len(line)


if __name__ == "__main__":
    unittest.main()
