from __future__ import absolute_import

import ast
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW_PATH = os.path.join(ROOT, "ui", "qt_submitter_window.py")
CONTROLLER_PATH = os.path.join(ROOT, "ui", "controllers", "targeting_controller.py")

TARGETING_METHODS = (
    "load_worker_pools",
    "save_worker_pools",
    "normalize_pools",
    "pool_assignment_strategy",
    "pool_assignment_strategy_key",
    "pool_record_by_id",
    "pool_names_from_ids",
    "selected_pool_ids",
    "excluded_pool_ids",
    "effective_pool_records",
    "effective_pool_worker_ids",
    "active_pool_workers",
    "worker_data_is_stale",
    "online_pool_workers",
    "eligible_workers",
    "eligible_worker_ids",
    "update_pool_selection_widgets",
    "update_worker_sync_chips",
    "update_worker_targeting_summary",
    "update_pool_strategy_ui",
    "on_pool_strategy_changed",
    "on_selected_pools_changed",
    "on_excluded_pools_changed",
    "worker_provider",
    "normalize_workers",
    "sync_available_workers",
    "on_workers_synced",
    "on_worker_sync_failed",
    "on_worker_sync_finished",
    "apply_available_workers",
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


class TargetingControllerSplitStaticTests(unittest.TestCase):
    def test_targeting_controller_is_present_and_mixed_into_window(self):
        self.assertTrue(os.path.isfile(CONTROLLER_PATH))
        submitter, window_methods = _class_methods(WINDOW_PATH, "RenderHiveSubmitter")
        bases = {ast.unparse(base) for base in submitter.bases}
        self.assertIn("TargetingControllerMixin", bases)

        controller, controller_methods = _class_methods(
            CONTROLLER_PATH,
            "TargetingControllerMixin",
        )
        self.assertIsNotNone(controller)
        for method_name in TARGETING_METHODS:
            self.assertNotIn(method_name, window_methods)
            self.assertIn(method_name, controller_methods)

    def test_removed_legacy_pool_dialog_path_is_not_kept_in_controller(self):
        with open(CONTROLLER_PATH, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertNotIn("def refresh_pool_combo", content)
        self.assertNotIn("def manage_worker_pools", content)
        self.assertNotIn("def selected_pool_id(", content)
        self.assertNotIn("def selected_pool_worker_ids(", content)
        self.assertNotIn("self.on_pool_changed", content)

    def test_installer_and_audit_require_targeting_controller(self):
        expression = 'os.path.join("ui", "controllers", "targeting_controller.py")'
        for relative_path in (
            "renderhive_installer.py",
            os.path.join("tools", "production_audit.py"),
        ):
            with open(os.path.join(ROOT, relative_path), "r", encoding="utf-8") as handle:
                self.assertIn(expression, handle.read())


if __name__ == "__main__":
    unittest.main()
