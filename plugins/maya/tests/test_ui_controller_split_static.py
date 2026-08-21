from __future__ import absolute_import

import ast
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_ROOT = os.path.join(ROOT, "ui")
WINDOW_PATH = os.path.join(UI_ROOT, "qt_submitter_window.py")
API_CONTROLLER_PATH = os.path.join(UI_ROOT, "controllers", "api_controller.py")
REGISTRY_PATH = os.path.join(UI_ROOT, "runtime_registry.py")

API_METHODS = (
    "api_enabled",
    "load_api_settings",
    "api_settings_payload",
    "save_api_settings",
    "set_api_status",
    "open_api_config",
    "test_api_connection",
    "on_api_test_succeeded",
    "on_api_test_failed",
    "on_api_test_finished",
    "prepare_api_task",
    "submit_job",
    "on_api_submit_succeeded",
    "on_api_submit_failed",
    "on_api_submit_finished",
)


def _class_methods(path, class_name):
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    class_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return class_node, {
        node.name: node for node in class_node.body
        if isinstance(node, ast.FunctionDef)
    }


class UiControllerSplitStaticTests(unittest.TestCase):
    def test_api_controller_and_registry_modules_are_present(self):
        self.assertTrue(os.path.isfile(API_CONTROLLER_PATH))
        self.assertTrue(os.path.isfile(REGISTRY_PATH))
        self.assertTrue(os.path.isfile(os.path.join(UI_ROOT, "controllers", "__init__.py")))

    def test_submitter_uses_api_controller_mixin(self):
        submitter, methods = _class_methods(WINDOW_PATH, "RenderHiveSubmitter")
        bases = {ast.unparse(base) for base in submitter.bases}
        self.assertIn("QtWidgets.QDialog", bases)
        self.assertIn("ApiControllerMixin", bases)
        for method_name in API_METHODS:
            self.assertNotIn(method_name, methods)

        controller, controller_methods = _class_methods(
            API_CONTROLLER_PATH,
            "ApiControllerMixin",
        )
        self.assertIsNotNone(controller)
        for method_name in API_METHODS:
            self.assertIn(method_name, controller_methods)

    def test_widget_registry_has_stable_identity(self):
        with open(WINDOW_PATH, "r", encoding="utf-8") as handle:
            source = handle.read()
        with open(REGISTRY_PATH, "r", encoding="utf-8") as handle:
            registry = handle.read()
        with open(API_CONTROLLER_PATH, "r", encoding="utf-8") as handle:
            controller = handle.read()

        self.assertIn("from .runtime_registry import WIDGETS", source)
        self.assertIn("_WIDGETS = WIDGETS", source)
        self.assertNotIn("_WIDGETS = {}", source)
        self.assertGreaterEqual(source.count("_WIDGETS.clear()"), 2)
        self.assertIn("WIDGETS = {}", registry)
        self.assertIn("from ..runtime_registry import WIDGETS as _WIDGETS", controller)

    def test_api_controller_keeps_async_thread_lifecycle(self):
        with open(API_CONTROLLER_PATH, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("WorkerSyncThread", source)
        self.assertIn("self.api_test_thread.succeeded.connect", source)
        self.assertIn("self.api_submit_thread.succeeded.connect", source)
        self.assertIn("self.api_submit_thread.deleteLater()", source)
        self.assertIn("self.api_submit_thread = None", source)

    def test_installer_and_audit_require_controller_modules(self):
        required = (
            'os.path.join("ui", "runtime_registry.py")',
            'os.path.join("ui", "controllers", "__init__.py")',
            'os.path.join("ui", "controllers", "api_controller.py")',
        )
        for relative_path in (
            "renderhive_installer.py",
            os.path.join("tools", "production_audit.py"),
        ):
            with open(os.path.join(ROOT, relative_path), "r", encoding="utf-8") as handle:
                source = handle.read()
            for expression in required:
                self.assertIn(expression, source)


if __name__ == "__main__":
    unittest.main()
