from __future__ import absolute_import

import unittest
from api import maya_bridge


class DummyApi(object):
    pass


class BridgeExportTests(unittest.TestCase):
    def test_managed_config_helpers_are_installed(self):
        api = DummyApi()
        maya_bridge.install(api)
        self.assertTrue(callable(api.api_admin_mode_enabled))
        self.assertTrue(callable(api.get_api_config_source))
        self.assertTrue(callable(api.get_api_layer_tasks))
        self.assertTrue(callable(api.get_api_layer_task))


if __name__ == "__main__":
    unittest.main()
