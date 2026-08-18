from __future__ import annotations

import unittest
from pathlib import Path


class GPUUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.app = (cls.root / "app.py").read_text(encoding="utf-8")
        cls.widgets = (cls.root / "ui" / "widgets.py").read_text(encoding="utf-8")
        cls.spec = (cls.root / "RenderHiveWorker.spec").read_text(encoding="utf-8")

    def test_worker_uses_cached_gpu_detector(self):
        self.assertIn("from core.gpu_info import GPUDetector", self.app)
        self.assertIn("self.gpu_detector = GPUDetector()", self.app)
        self.assertIn("info.update(self.gpu_detector.query())", self.app)
        self.assertIn("self.local_gpu_detector = GPUDetector()", self.app)
        self.assertIn("snapshot.update(self.local_gpu_detector.query())", self.app)

    def test_generic_gpu_shows_na_instead_of_fake_zero(self):
        self.assertIn("def set_unavailable", self.widgets)
        self.assertIn('self.value_label.setText("N/A")', self.widgets)
        self.assertIn("gpu_telemetry_available", self.app)
        self.assertIn("N/A", self.app)

    def test_gpu_module_is_explicitly_packaged(self):
        self.assertIn('"core.gpu_info"', self.spec)


if __name__ == "__main__":
    unittest.main()
