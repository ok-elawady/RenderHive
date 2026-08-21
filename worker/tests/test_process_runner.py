import os
import tempfile
import unittest
import sys

from core.process_runner import _resolve_executable, run_process


class ProcessRunnerTests(unittest.TestCase):
    def test_missing_executable_reports_the_real_command(self):
        with self.assertRaises(FileNotFoundError) as context:
            _resolve_executable(["renderhive_missing_executable_12345", "--test"], {"PATH": ""})
        message = str(context.exception)
        self.assertIn("renderhive_missing_executable_12345", message)
        self.assertIn("Full task command", message)

    def test_absolute_executable_is_kept(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = os.path.join(temp_dir, "tool.exe")
            with open(executable, "wb") as handle:
                handle.write(b"MZ")
            command = _resolve_executable([executable, "--test"], os.environ.copy())
            self.assertEqual(command[0], executable)

    def test_run_process_publishes_lifecycle_and_output_callbacks(self):
        events = []
        lines = []
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_process(
                command=[sys.executable, "-c", "print('RENDERHIVE_FRAME_DONE frame=1 index=1 total=1')"],
                task_id="progress-callback-test",
                env={},
                cwd=temp_dir,
                is_cancelled=lambda: False,
                heartbeat=lambda: None,
                log=lambda _message: None,
                line_callback=lines.append,
                event_callback=events.append,
            )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("resolving_executable", events)
        self.assertIn("starting_process", events)
        self.assertIn("process_started", events)
        self.assertTrue(any("RENDERHIVE_FRAME_DONE" in line for line in lines))
        self.assertGreaterEqual(result.peak_memory_mb, 0)


if __name__ == "__main__":
    unittest.main()
