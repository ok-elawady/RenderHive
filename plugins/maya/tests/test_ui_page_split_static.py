from __future__ import absolute_import

import ast
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_ROOT = os.path.join(ROOT, "ui")
WINDOW_PATH = os.path.join(UI_ROOT, "qt_submitter_window.py")


class UiPageSplitStaticTests(unittest.TestCase):
    def test_page_builder_modules_are_present(self):
        expected = (
            os.path.join("pages", "job_page.py"),
            os.path.join("pages", "render_page.py"),
            os.path.join("pages", "validation_page.py"),
            os.path.join("pages", "tools_page.py"),
        )
        for relative_path in expected:
            self.assertTrue(os.path.isfile(os.path.join(UI_ROOT, relative_path)))

    def test_main_window_delegates_page_construction(self):
        with open(WINDOW_PATH, "r", encoding="utf-8") as handle:
            source = handle.read()
        tree = ast.parse(source)
        submitter = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "RenderHiveSubmitter"
        )
        expected = {
            "build_job_page": "build_job_page_view",
            "build_render_page": "build_render_page_view",
            "build_checks_page": "build_checks_page_view",
            "build_more_page": "build_more_page_view",
        }
        methods = {
            node.name: node for node in submitter.body
            if isinstance(node, ast.FunctionDef)
        }
        for method_name, delegate_name in expected.items():
            method = methods[method_name]
            self.assertLessEqual(len(method.body), 2)
            self.assertIn(delegate_name, ast.dump(method, include_attributes=False))

    def test_page_builders_keep_expected_sections(self):
        checks = {
            "job_page.py": ("Job Configuration", "Scheduling", "Pool Selection"),
            "render_page.py": ("Render Configuration", "Render Layers"),
            "validation_page.py": ("Validation", "Fix All Safe Issues"),
            "tools_page.py": ("Tools", "Activity Log"),
        }
        for filename, labels in checks.items():
            path = os.path.join(UI_ROOT, "pages", filename)
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
            for label in labels:
                self.assertIn(label, source)

    def test_installer_and_audit_require_page_modules(self):
        required = (
            'os.path.join("ui", "pages", "job_page.py")',
            'os.path.join("ui", "pages", "render_page.py")',
            'os.path.join("ui", "pages", "validation_page.py")',
            'os.path.join("ui", "pages", "tools_page.py")',
        )
        for relative_path in ("renderhive_installer.py", os.path.join("tools", "production_audit.py")):
            with open(os.path.join(ROOT, relative_path), "r", encoding="utf-8") as handle:
                source = handle.read()
            for expression in required:
                self.assertIn(expression, source)


if __name__ == "__main__":
    unittest.main()
