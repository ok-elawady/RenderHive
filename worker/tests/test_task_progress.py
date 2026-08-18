from __future__ import annotations

import time
import unittest

from core.progress import TaskProgressTracker


class TaskProgressTrackerTests(unittest.TestCase):
    def test_explicit_houdini_markers_produce_exact_multiframe_progress(self):
        tracker = TaskProgressTracker(1, 4, 1, started_at=time.monotonic() - 20.0)
        tracker.on_line("RENDERHIVE_FRAME_START frame=1 index=1 total=4")
        first = tracker.on_line("RENDERHIVE_FRAME_DONE frame=1 index=1 total=4")
        self.assertEqual(first.completed_frames, 1)
        self.assertEqual(first.percent, 25)
        self.assertEqual(first.current_frame, 1)

        second = tracker.on_line("RENDERHIVE_FRAME_DONE frame=2 index=2 total=4")
        self.assertEqual(second.completed_frames, 2)
        self.assertEqual(second.percent, 50)
        self.assertGreater(second.eta_seconds or 0, 0)

    def test_single_frame_renderer_percentage_maps_between_setup_and_write(self):
        tracker = TaskProgressTracker(1, 1, 1)
        snapshot = tracker.on_line("Arnold rendering progress 50%")
        self.assertEqual(snapshot.phase, "Rendering")
        self.assertEqual(snapshot.renderer_percent, 50.0)
        self.assertGreaterEqual(snapshot.percent, 55)
        self.assertLess(snapshot.percent, 92)

    def test_multiframe_image_write_does_not_jump_whole_chunk_to_ninety_percent(self):
        tracker = TaskProgressTracker(1, 4, 1)
        tracker.on_line("RENDERHIVE_FRAME_START frame=1 index=1 total=4")
        snapshot = tracker.on_line("Writing output image C:/renders/test.0001.exr")
        self.assertEqual(snapshot.phase, "Rendering")
        self.assertLess(snapshot.percent, 30)

    def test_phase_progress_is_monotonic(self):
        tracker = TaskProgressTracker(1, 1, 1)
        writing = tracker.on_line("Writing output image C:/renders/test.0001.exr")
        self.assertEqual(writing.phase, "Writing Output")
        self.assertGreaterEqual(writing.percent, 92)
        later_noise = tracker.on_line("Arnold rendering frame 1")
        self.assertEqual(later_noise.phase, "Writing Output")
        self.assertGreaterEqual(later_noise.percent, writing.percent)

    def test_process_events_report_launch_phases(self):
        tracker = TaskProgressTracker(1, 1, 1)
        self.assertEqual(tracker.on_process_event("resolving_executable").phase, "Resolving Executable")
        self.assertEqual(tracker.on_process_event("starting_process").phase, "Launching Renderer")
        self.assertEqual(tracker.on_process_event("process_started").phase, "Loading Scene")

    def test_finish_success_is_one_hundred_percent(self):
        tracker = TaskProgressTracker(1, 3, 1)
        result = tracker.finish(True)
        self.assertEqual(result.phase, "Complete")
        self.assertEqual(result.percent, 100)
        self.assertEqual(result.completed_frames, 3)
        self.assertEqual(result.eta_seconds, 0.0)

    def test_failure_preserves_last_real_percentage(self):
        tracker = TaskProgressTracker(1, 1, 1)
        tracker.on_line("Render progress 40%")
        before = tracker.snapshot().percent
        result = tracker.finish(False)
        self.assertEqual(result.phase, "Failed")
        self.assertEqual(result.percent, before)


if __name__ == "__main__":
    unittest.main()
