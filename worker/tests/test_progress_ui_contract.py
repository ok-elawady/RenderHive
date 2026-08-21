from __future__ import annotations

import unittest
from pathlib import Path


class ProgressUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.main_window_text = (cls.root / "ui" / "main_window.py").read_text(encoding="utf-8")
        cls.worker_thread_text = (cls.root / "daemon" / "worker_thread.py").read_text(encoding="utf-8")
        cls.runner_text = (cls.root / "core" / "process_runner.py").read_text(encoding="utf-8")
        cls.houdini_text = (cls.root / "render_scripts" / "houdini_render_rop.py").read_text(encoding="utf-8")

    def test_current_task_has_production_progress_labels(self):
        for text in (
            "self.job_phase_label",
            "self.job_percent_label",
            "self.job_frame_label",
            "self.job_eta_label",
            "Remaining: Estimating…",
        ):
            self.assertIn(text, self.main_window_text)

    def test_process_runner_publishes_lifecycle_events(self):
        self.assertIn('event_callback("resolving_executable")', self.runner_text)
        self.assertIn('event_callback("starting_process")', self.runner_text)
        self.assertIn('event_callback("process_started")', self.runner_text)

    def test_houdini_script_prints_exact_frame_markers(self):
        self.assertIn("RENDERHIVE_FRAME_START", self.houdini_text)
        self.assertIn("RENDERHIVE_FRAME_DONE", self.houdini_text)
        self.assertIn("for index, frame in enumerate(frames, 1)", self.houdini_text)

    def test_progress_is_exposed_in_worker_heartbeat_system_info(self):
        self.assertIn('info["current_task"]', self.worker_thread_text)
        self.assertIn('"progress_percent"', self.worker_thread_text)
        self.assertIn('"eta_seconds"', self.worker_thread_text)


class SmoothProgressUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.main_window_text = (root / "ui" / "main_window.py").read_text(encoding="utf-8")

    def test_visual_timer_and_high_resolution_bar_are_present(self):
        self.assertIn("self.progress_animation_timer.setInterval(25)", self.main_window_text)
        self.assertIn("self.job_progress.setRange(0, 1000)", self.main_window_text)
        self.assertIn("self._animate_progress_tick", self.main_window_text)

    def test_ui_does_not_jump_directly_to_renderer_percent(self):
        self.assertIn("self.current_progress_target = max", self.main_window_text)
        self.assertIn("self.progress_animator.set_target", self.main_window_text)


if __name__ == "__main__":
    unittest.main()
