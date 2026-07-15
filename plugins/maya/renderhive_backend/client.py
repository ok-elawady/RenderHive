from __future__ import absolute_import

import json
import socket
import ssl

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError

from .config import normalize_config
from .errors import (
    BackendConnectionError,
    BackendHTTPError,
    BackendResponseError,
)


class BackendClient(object):
    def __init__(self, config):
        self.config = normalize_config(config)

    @property
    def base_url(self):
        return self.config["base_url"]

    @property
    def timeout(self):
        return int(self.config.get("timeout_seconds", 15))

    def _endpoint(self, name, **values):
        path = self.config.get("endpoints", {}).get(name)

        if not path:
            raise BackendResponseError(
                "Backend endpoint is not configured: {}".format(name)
            )

        try:
            path = str(path).format(**values)
        except KeyError as error:
            raise BackendResponseError(
                "Missing endpoint value {} for {}".format(error, name)
            )

        if path.startswith(("http://", "https://")):
            return path

        return "{}/{}".format(
            self.base_url.rstrip("/"),
            path.lstrip("/")
        )

    def _headers(self):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RenderHive-Maya-Submitter/1.5",
        }

        auth = self.config.get("auth", {})
        auth_type = str(auth.get("type") or "token").lower()
        token = str(auth.get("token") or "").strip()

        if token and auth_type == "token":
            headers["Authorization"] = "Token {}".format(token)
        elif token and auth_type == "x-session-token":
            headers["X-Session-Token"] = token

        return headers

    def _ssl_context(self):
        if self.config.get("verify_ssl", True):
            return None

        try:
            return ssl._create_unverified_context()
        except Exception:
            return None

    @staticmethod
    def _decode_response(raw):
        if raw is None:
            return {}

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        raw = str(raw).strip()
        if not raw:
            return {}

        try:
            return json.loads(raw)
        except Exception:
            return {"message": raw}

    @staticmethod
    def _error_message(payload, status_code):
        if isinstance(payload, dict):
            for key in ("detail", "message", "error", "non_field_errors"):
                value = payload.get(key)
                if isinstance(value, list):
                    value = "; ".join(str(item) for item in value)
                if value:
                    return str(value)

            field_messages = []
            for key, value in payload.items():
                if isinstance(value, list):
                    value = "; ".join(str(item) for item in value)
                elif isinstance(value, dict):
                    value = json.dumps(value, sort_keys=True)
                if value:
                    field_messages.append("{}: {}".format(key, value))

            if field_messages:
                return " | ".join(field_messages)

        return "Backend returned HTTP {}.".format(status_code)

    def request(
        self,
        method,
        endpoint_name,
        payload=None,
        endpoint_values=None,
    ):
        url = self._endpoint(
            endpoint_name,
            **(endpoint_values or {})
        )

        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        request = Request(
            url,
            data=body,
            headers=self._headers()
        )
        request.get_method = lambda: str(method).upper()

        try:
            response = urlopen(
                request,
                timeout=self.timeout,
                context=self._ssl_context()
            )
            status_code = getattr(response, "status", None) or response.getcode()
            data = self._decode_response(response.read())

            return {
                "ok": 200 <= int(status_code) < 300,
                "status_code": int(status_code),
                "data": data,
                "url": url,
            }

        except HTTPError as error:
            payload_data = self._decode_response(error.read())
            raise BackendHTTPError(
                error.code,
                self._error_message(payload_data, error.code),
                payload=payload_data,
            )

        except (URLError, socket.timeout) as error:
            reason = getattr(error, "reason", error)
            raise BackendConnectionError(
                "Cannot connect to {}: {}".format(url, reason)
            )

        except Exception as error:
            raise BackendConnectionError(
                "Backend request failed: {}".format(error)
            )

    def test_connection(self):
        # The OpenAPI document does not define /health. An authenticated,
        # paginated jobs request is therefore used as the connection test.
        return self.request("GET", "connection_test")

    def list_jobs(self):
        return self.request("GET", "jobs").get("data", {})

    def submit_job(self, payload):
        response = self.request("POST", "jobs", payload=payload)
        data = response.get("data", {})

        if not isinstance(data, dict):
            raise BackendResponseError(
                "Job submission response must be a JSON object."
            )

        return data

    def get_job_status(self, job_id):
        return self.request(
            "GET",
            "job_status",
            endpoint_values={"job_id": job_id},
        ).get("data", {})

    def pause_job(self, job_id):
        return self.request(
            "POST",
            "job_pause",
            payload={},
            endpoint_values={"job_id": job_id},
        ).get("data", {})

    def resume_job(self, job_id):
        return self.request(
            "POST",
            "job_resume",
            payload={},
            endpoint_values={"job_id": job_id},
        ).get("data", {})

    def delete_job(self, job_id):
        return self.request(
            "DELETE",
            "job_delete",
            endpoint_values={"job_id": job_id},
        )
