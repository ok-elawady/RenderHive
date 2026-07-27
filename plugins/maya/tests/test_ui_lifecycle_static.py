from __future__ import print_function

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class UiLifecycleStaticTests(unittest.TestCase):
    def read(self, relative):
        with open(os.path.join(ROOT, relative), 'r', encoding='utf-8') as handle:
            return handle.read()

    def test_submitter_does_not_reload_qt_modules(self):
        content = self.read('renderhive_maya_submitter.py')
        self.assertNotIn('importlib.reload(qt_submitter_window)', content)
        self.assertNotIn('importlib.reload(qt_theme)', content)

    def test_menu_command_does_not_reload_submitter(self):
        content = self.read('renderhive_installer.py')
        self.assertNotIn('importlib.reload(renderhive_maya_submitter)', content)

    def test_close_detaches_running_threads(self):
        content = self.read(os.path.join('ui', 'qt_submitter_window.py'))
        self.assertIn('def _detach_running_thread', content)
        self.assertIn('_BACKGROUND_THREADS', content)
        self.assertIn('thread.requestInterruption()', content)

    def test_window_is_reused(self):
        content = self.read(os.path.join('ui', 'qt_submitter_window.py'))
        self.assertIn('if isValid(_WINDOW) and not _WINDOW._is_closing', content)
        self.assertNotIn('_WINDOW.close()\n            _WINDOW.deleteLater()', content)


if __name__ == '__main__':
    unittest.main()
