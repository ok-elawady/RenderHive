from __future__ import absolute_import

import datetime
import json
import threading
import unittest

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from api.client import RenderHiveApiClient
from api.config import DEFAULT_CONFIG
from api.errors import ApiAuthenticationError


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _send(self, code, payload=None):
        raw = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/api/jobs/job-1/layers/layer-1/tasks/":
            self._send(200, {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{"id": "task-1", "name": "beauty_0001"}],
            })
            return

        if self.path == "/api/jobs/job-1/layers/layer-1/tasks/task-1/":
            self._send(200, {"id": "task-1", "name": "beauty_0001"})
            return

        if self.path.startswith("/api/jobs/"):
            if self.headers.get("Authorization") != "Token test-token":
                self._send(401, {"detail": "Invalid token"})
                return
            self._send(200, {
                "count": 0,
                "next": None,
                "previous": None,
                "results": [],
            })
            return

        if self.path == "/api/workers/":
            self._send(200, {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{
                    "id": 1,
                    "hostname": "worker-01",
                    "pools": [],
                    "created_at": "2026-07-24T00:00:00Z",
                    "last_ping": "2026-07-24T00:00:00Z",
                }],
            })
            return

        self._send(404, {"detail": "Not found"})

    def do_DELETE(self):
        if self.path == "/api/jobs/job-1/":
            self._send(204)
            return
        self._send(404, {"detail": "Not found"})


class ApiClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def make_client(self, token="test-token"):
        config = json.loads(json.dumps(DEFAULT_CONFIG))
        config["base_url"] = "http://127.0.0.1:{}".format(
            self.server.server_port
        )
        config["auth"]["token"] = token
        return RenderHiveApiClient(config)

    def test_token_auth_and_connection(self):
        response = self.make_client().test_connection()
        self.assertEqual(response["status_code"], 200)
        self.assertTrue(response["request_id"])

    def test_worker_pagination(self):
        workers = self.make_client().list_workers()
        self.assertEqual(len(workers), 1)
        self.assertEqual(workers[0]["hostname"], "worker-01")

    def test_nested_task_endpoints(self):
        client = self.make_client()
        tasks = client.list_layer_tasks("job-1", "layer-1")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], "task-1")
        detail = client.get_layer_task("job-1", "layer-1", "task-1")
        self.assertEqual(detail["name"], "beauty_0001")

    def test_authentication_error(self):
        with self.assertRaises(ApiAuthenticationError):
            self.make_client(token="wrong").test_connection()

    def test_delete_204(self):
        response = self.make_client().delete_job("job-1")
        self.assertEqual(response["status_code"], 204)
        self.assertEqual(response["data"], {})

    def test_created_job_resolution_prefers_task_uid(self):
        client = self.make_client()
        now = datetime.datetime.now(datetime.timezone.utc)
        client.list_all_jobs = lambda: [
            {
                "id": "job-newer-wrong",
                "visible_name": "Shot01",
                "project": "Show",
                "user": "artist",
                "created_at": now.isoformat(),
            },
            {
                "id": "job-correct",
                "visible_name": "Shot01",
                "project": "Show",
                "user": "artist",
                "created_at": (now - datetime.timedelta(seconds=1)).isoformat(),
            },
        ]
        details = {
            "job-newer-wrong": {
                "id": "job-newer-wrong",
                "layers": [{"scene_info": {"task_uid": "OTHER"}}],
            },
            "job-correct": {
                "id": "job-correct",
                "layers": [{"scene_info": {"task_uid": "RH-UNIQUE"}}],
            },
        }
        client.get_job_status = lambda job_id: details[job_id]
        payload = {
            "visible_name": "Shot01",
            "project": "Show",
            "user": "artist",
            "layers": [{"scene_info": {"task_uid": "RH-UNIQUE"}}],
        }
        resolved = client._resolve_created_job(payload, submitted_after=now)
        self.assertEqual(resolved["id"], "job-correct")


if __name__ == "__main__":
    unittest.main()
