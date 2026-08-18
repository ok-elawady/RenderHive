from __future__ import absolute_import

import os
import unittest


class InfoTooltipPolicyTests(unittest.TestCase):
    def test_explanatory_widget_tooltips_only_live_on_info_icon(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ui_root = os.path.join(root, "ui")
        common_path = os.path.join(ui_root, "common_widgets.py")

        with open(common_path, "r", encoding="utf-8") as handle:
            common_source = handle.read()

        info_start = common_source.index("class InfoTipButton")
        info_end = common_source.index("class LabeledField")

        for filename in (
            "common_widgets.py",
            "targeting_widgets.py",
            "qt_submitter_window.py",
        ):
            path = os.path.join(ui_root, filename)
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()

            offset = 0
            for line_number, line in enumerate(source.splitlines(True), 1):
                stripped = line.strip()

                if ".setToolTip(" not in stripped:
                    offset += len(line)
                    continue

                if filename == "common_widgets.py" and stripped.startswith(
                    "self.setToolTip("
                ):
                    self.assertTrue(
                        info_start <= offset < info_end,
                        "Unexpected widget tooltip at {}:{}: {}".format(
                            filename,
                            line_number,
                            stripped,
                        ),
                    )
                else:
                    self.assertTrue(
                        stripped.startswith("item.setToolTip(")
                        or stripped.startswith("pool_item.setToolTip("),
                        "Unexpected widget tooltip at {}:{}: {}".format(
                            filename,
                            line_number,
                            stripped,
                        ),
                    )

                offset += len(line)


if __name__ == "__main__":
    unittest.main()
