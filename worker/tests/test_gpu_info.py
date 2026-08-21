from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.gpu_info import (
    _normalize_cim_payload,
    nvidia_smi_candidates,
    parse_nvidia_smi_csv,
    summarize_gpu_rows,
)


class GPUInfoTests(unittest.TestCase):
    def test_parses_nvidia_smi_rows(self):
        rows = parse_nvidia_smi_csv(
            "NVIDIA GeForce RTX 4090, 24564, 2048, 37\n"
            "NVIDIA RTX A4000, 16376, 4096, 81\n"
        )
        self.assertEqual([row["name"] for row in rows], ["NVIDIA GeForce RTX 4090", "NVIDIA RTX A4000"])
        self.assertEqual(rows[0]["vram_mb"], 24564)
        self.assertEqual(rows[1]["utilization_percent"], 81.0)
        self.assertTrue(rows[0]["telemetry_available"])

    def test_known_windows_system32_path_is_discovered(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "System32" / "nvidia-smi.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"fake")
            with mock.patch("core.gpu_info.shutil.which", return_value=None):
                result = nvidia_smi_candidates({"SystemRoot": folder})
            self.assertEqual(result, [os.path.normcase(os.path.abspath(str(executable)))])

    def test_cim_fallback_detects_non_nvidia_adapter(self):
        rows = _normalize_cim_payload(
            [
                {"Name": "AMD Radeon RX 7900 XTX", "AdapterRAM": 4294967295},
                {"Name": "Microsoft Basic Render Driver", "AdapterRAM": 0},
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "AMD Radeon RX 7900 XTX")
        self.assertFalse(rows[0]["telemetry_available"])

    def test_summary_populates_heartbeat_fields(self):
        result = summarize_gpu_rows(
            [{"name": "Intel Arc A770", "vram_mb": 0, "vram_used_mb": 0, "utilization_percent": None, "telemetry_available": False}],
            "windows-cim",
        )
        self.assertEqual(result["gpu_models"], ["Intel Arc A770"])
        self.assertEqual(result["gpu_name"], "Intel Arc A770")
        self.assertEqual(result["gpu_detection_source"], "windows-cim")
        self.assertFalse(result["gpu_telemetry_available"])


if __name__ == "__main__":
    unittest.main()
