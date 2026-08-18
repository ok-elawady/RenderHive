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

    def test_api_0_2_ui_does_not_expose_unimplemented_scheduler_options(self):
        content = self.read(os.path.join('ui', 'qt_submitter_window.py'))
        self.assertNotIn('Smart Package', content)
        self.assertNotIn('Full Package', content)
        self.assertNotIn('LabeledField("Machine Limit"', content)
        self.assertNotIn('Start Suspended', content)
        self.assertNotIn('rh_start_suspended', content)
        self.assertIn('rh_minimum_cores', content)
        self.assertIn('rh_minimum_ram_gb', content)
        self.assertIn('rh_minimum_gpus', content)

    def test_multi_render_layer_ui_is_wired(self):
        content = self.read(os.path.join('ui', 'qt_submitter_window.py'))
        render_page = self.read(os.path.join('ui', 'pages', 'render_page.py'))
        targeting = self.read(os.path.join('ui', 'targeting_widgets.py'))
        submitter = self.read('renderhive_maya_submitter.py')
        payload = self.read(os.path.join('api', 'payload.py'))
        self.assertIn('class RenderLayerSelector', targeting)
        self.assertIn('from .targeting_widgets import RenderLayerSelector', content)
        self.assertIn('register("rh_render_layers", RenderLayerSelector())', render_page)
        self.assertIn('def refresh_render_layers', content)
        self.assertIn('"rh_render_layers",', content)
        self.assertIn('def get_render_layers', submitter)
        self.assertIn('setup.getRenderLayers()', submitter)
        self.assertIn('RENDERHIVE_MAYA_RENDER_LAYER', payload)
        self.assertIn('parts.extend(["-rl", _quote(render_layer)])', payload)
        self.assertIn('"{} Selected / {} Available"', targeting)
        self.assertIn('self.refresh_render_layers(record_activity=False)', content)
        task_builder = self.read(os.path.join('submission', 'task_builder.py'))
        self.assertIn('render_layer_missing_names', task_builder)
        self.assertIn('defaultRenderLayer (Beauty / Master)', submitter)


    def test_ui_cleanup_modules_are_wired(self):
        content = self.read(os.path.join('ui', 'qt_submitter_window.py'))
        common = self.read(os.path.join('ui', 'common_widgets.py'))
        targeting = self.read(os.path.join('ui', 'targeting_widgets.py'))
        worker_data = self.read(os.path.join('ui', 'worker_data.py'))

        targeting_controller = self.read(os.path.join('ui', 'controllers', 'targeting_controller.py'))

        self.assertIn('from .common_widgets import (', content)
        self.assertIn('from .targeting_widgets import RenderLayerSelector', content)
        self.assertIn('TargetingControllerMixin', content)
        self.assertIn('from ..worker_data import (', targeting_controller)
        self.assertIn('class InfoTipButton', common)
        self.assertIn('class PoolSelectionDialog', targeting)
        self.assertNotIn('class WorkerSelectionDialog', targeting)
        self.assertIn('def worker_identifier', worker_data)
        self.assertNotIn('class PoolSelectionDialog', content)
        self.assertNotIn('class WorkerSelectionDialog', content)
        self.assertNotIn('class InfoTipButton', content)

        installer = self.read('renderhive_installer.py')
        self.assertIn('os.path.join("ui", "common_widgets.py")', installer)
        self.assertIn('os.path.join("ui", "targeting_widgets.py")', installer)
        self.assertIn('os.path.join("ui", "worker_data.py")', installer)
        self.assertIn('os.path.join("ui", "controllers", "targeting_controller.py")', installer)



if __name__ == '__main__':
    unittest.main()
