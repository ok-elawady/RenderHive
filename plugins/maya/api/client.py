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
    ApiConnectionError,
    ApiHttpError,
    ApiResponseError,
)


class RenderHiveApiClient(object):
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
            raise ApiResponseError(
                "API endpoint is not configured: {}".format(name)
            )

        try:
            path = str(path).format(**values)
        except KeyError as error:
            raise ApiResponseError(
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
            "User-Agent": "RenderHive-Maya-Submitter/1.8",
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

        return "RenderHive API returned HTTP {}.".format(status_code)

    def _request_url(self, method, url, payload=None):
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
            raise ApiHttpError(
                error.code,
                self._error_message(payload_data, error.code),
                payload=payload_data,
            )

        except (URLError, socket.timeout) as error:
            reason = getattr(error, "reason", error)
            raise ApiConnectionError(
                "Cannot connect to {}: {}".format(url, reason)
            )

        except Exception as error:
            raise ApiConnectionError(
                "RenderHive API request failed: {}".format(error)
            )

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
        return self._request_url(method, url, payload=payload)

    def test_connection(self):
        # The OpenAPI document does not define /health. An authenticated,
        # paginated jobs request is therefore used as the connection test.
        return self.request("GET", "connection_test")

    @staticmethod
    def _extract_list(payload, keys=("results", "items", "data")):
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        return []

    def _list_all_pages(self, endpoint_name, list_keys):
        url = self._endpoint(endpoint_name)
        items = []
        visited = set()

        while url and url not in visited:
            visited.add(url)
            response = self._request_url("GET", url)
            payload = response.get("data", {})
            items.extend(self._extract_list(payload, keys=list_keys))

            if isinstance(payload, dict):
                next_url = payload.get("next")
            else:
                next_url = None

            if next_url and not str(next_url).startswith(("http://", "https://")):
                next_url = "{}/{}".format(
                    self.base_url.rstrip("/"),
                    str(next_url).lstrip("/"),
                )

            url = next_url

        return items

    def list_jobs(self):
        return self.request("GET", "jobs").get("data", {})

    def list_workers(self):
        return self._list_all_pages(
            "workers",
            ("results", "workers", "items", "data"),
        )

    def get_worker(self, worker_id):
        return self.request(
            "GET",
            "worker_detail",
            endpoint_values={"worker_id": worker_id},
        ).get("data", {})

    def list_pools(self):
        return self._list_all_pages(
            "pools",
            ("results", "pools", "items", "data"),
        )

    def get_pool(self, pool_id):
        return self.request(
            "GET",
            "pool_detail",
            endpoint_values={"pool_id": pool_id},
        ).get("data", {})

    def create_pool(self, name, description=""):
        return self.request(
            "POST",
            "pools",
            payload={
                "name": str(name or "").strip(),
                "description": str(description or "").strip(),
            },
        ).get("data", {})

    def update_pool(self, pool_id, name=None, description=None):
        payload = {}
        if name is not None:
            payload["name"] = str(name).strip()
        if description is not None:
            payload["description"] = str(description).strip()

        return self.request(
            "PATCH",
            "pool_detail",
            payload=payload,
            endpoint_values={"pool_id": pool_id},
        ).get("data", {})

    def delete_pool(self, pool_id):
        return self.request(
            "DELETE",
            "pool_detail",
            endpoint_values={"pool_id": pool_id},
        )

    def _resolve_created_job(self, submitted_payload):
        jobs_payload = self.list_jobs()
        jobs = self._extract_list(
            jobs_payload,
            keys=("results", "jobs", "items", "data"),
        )

        visible_name = str(
            submitted_payload.get("visible_name") or ""
        ).strip()
        project = str(
            submitted_payload.get("project") or ""
        ).strip()
        user = str(
            submitted_payload.get("user") or ""
        ).strip()

        candidates = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            if visible_name and str(job.get("visible_name") or "") != visible_name:
                continue
            if project and str(job.get("project") or "") != project:
                continue
            if user and str(job.get("user") or "") != user:
                continue
            candidates.append(job)

        if not candidates:
            return {}

        candidates.sort(
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )
        return dict(candidates[0])

    def submit_job(self, payload):
        response = self.request("POST", "jobs", payload=payload)
        data = response.get("data", {})

        if not isinstance(data, dict):
            raise ApiResponseError(
                "Job submission response must be a JSON object."
            )

        job_id = data.get("id") or data.get("job_id") or data.get("uid")
        if not job_id:
            resolved = self._resolve_created_job(payload)
            if resolved:
                merged = dict(data)
                merged.update(resolved)
                merged["_renderhive_resolved_from_list"] = True
                data = merged

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
