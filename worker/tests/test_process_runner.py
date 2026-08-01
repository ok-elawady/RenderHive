import os
import tempfile
import unittest

from core.process_runner import _resolve_executable


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


if __name__ == "__main__":
    unittest.main()
