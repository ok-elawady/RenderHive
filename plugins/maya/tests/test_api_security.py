from __future__ import absolute_import

import unittest

from api.client import RenderHiveApiClient
from api.config import DEFAULT_CONFIG
from api.errors import ApiResponseError


class ApiSecurityTests(unittest.TestCase):
    def test_cross_origin_pagination_is_rejected(self):
        client = RenderHiveApiClient(DEFAULT_CONFIG)
        with self.assertRaises(ApiResponseError):
            client._assert_safe_url("https://example.com/api/workers/", source="pagination")

    def test_mutating_request_has_idempotency_header(self):
        client = RenderHiveApiClient(DEFAULT_CONFIG)
        headers = client._headers(request_id="abc", method="POST")
        self.assertEqual(headers["X-RenderHive-Idempotency-Key"], "abc")

    def test_connection_errors_keep_request_metadata(self):
        from api.errors import ApiConnectionError
        error = ApiConnectionError("failed", url="http://localhost", request_id="req")
        self.assertEqual(error.request_id, "req")
        self.assertEqual(error.url, "http://localhost")
