from __future__ import print_function

import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(relative_path):
    with open(os.path.join(ROOT, relative_path), "r", encoding="utf-8") as handle:
        return handle.read()


class UISurfacePolishStaticTests(unittest.TestCase):
    def test_job_dependency_inline_container_is_transparent_target(self):
        source = _read(os.path.join("ui", "pages", "job_page.py"))
        self.assertIn('dependency_widget.setObjectName("InlineFieldContainer")', source)
        self.assertIn('dependency_widget.setAutoFillBackground(False)', source)

    def test_render_layer_selector_has_specific_surface_targets(self):
        source = _read(os.path.join("ui", "targeting_widgets.py"))
        self.assertIn('self.setObjectName("RenderLayerSelector")', source)
        self.assertIn('self.setAutoFillBackground(False)', source)
        self.assertIn('self.tree.setObjectName("RenderLayerTree")', source)

    def test_job_dependency_browser_tree_has_specific_surface_target(self):
        source = _read(os.path.join("ui", "job_dependency_widgets.py"))
        self.assertIn('self.setObjectName("JobDependencyDialog")', source)
        self.assertIn('self.tree.setObjectName("JobDependencyTree")', source)

    def test_theme_uses_card_surfaces_not_terminal_black_for_targeted_widgets(self):
        theme = _read(os.path.join("ui", "qt_theme.py"))
        self.assertIn('QWidget#InlineFieldContainer,', theme)
        self.assertIn('QFrame#RenderLayerSelector {', theme)
        self.assertIn('QTreeWidget#RenderLayerTree,', theme)
        self.assertIn('QTreeWidget#JobDependencyTree {', theme)
        targeted_block = theme.split('QTreeWidget#RenderLayerTree,', 1)[1].split('QTreeWidget#RenderLayerTree::item,', 1)[0]
        self.assertIn('background-color: %(surface2)s;', targeted_block)
        self.assertNotIn('background-color: %(terminal)s;', targeted_block)


if __name__ == "__main__":
    unittest.main()

class CheckboxPolishStaticTests(unittest.TestCase):
    def test_checkbox_asset_is_packaged(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "ui", "icons", "check_mark.png")))

    def test_tree_and_checkbox_indicators_use_the_same_clean_mark(self):
        theme = _read(os.path.join("ui", "qt_theme.py"))
        self.assertIn('"check_mark": _qss_asset("check_mark.png")', theme)
        self.assertIn('QTreeWidget::indicator:checked {', theme)
        self.assertIn('QCheckBox::indicator:checked {', theme)
        self.assertGreaterEqual(theme.count('image: url("%(check_mark)s");'), 2)
