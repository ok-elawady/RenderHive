from __future__ import annotations

import unittest
from pathlib import Path


class GPUUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.worker_thread = (cls.root / "daemon" / "worker_thread.py").read_text(encoding="utf-8")
        cls.main_window = (cls.root / "ui" / "main_window.py").read_text(encoding="utf-8")
        cls.widgets = (cls.root / "ui" / "widgets.py").read_text(encoding="utf-8")
        cls.spec = (cls.root / "RenderHiveWorker.spec").read_text(encoding="utf-8")

    def test_worker_uses_cached_gpu_detector(self):
        self.assertIn("from core.gpu_info import GPUDetector", self.worker_thread)
        self.assertIn("self.gpu_detector = GPUDetector()", self.worker_thread)
        self.assertIn("info.update(self.gpu_detector.query())", self.worker_thread)
        self.assertIn("self.local_gpu_detector = GPUDetector()", self.main_window)
        self.assertIn("snapshot.update(self.local_gpu_detector.query())", self.main_window)

    def test_generic_gpu_shows_na_instead_of_fake_zero(self):
        self.assertIn("def set_unavailable", self.widgets)
        self.assertIn('self.value_label.setText("N/A")', self.widgets)
        self.assertIn("gpu_telemetry_available", self.main_window)
        self.assertIn("N/A", self.main_window)

    def test_gpu_module_is_explicitly_packaged(self):
        self.assertIn('"core.gpu_info"', self.spec)


if __name__ == "__main__":
    unittest.main()
