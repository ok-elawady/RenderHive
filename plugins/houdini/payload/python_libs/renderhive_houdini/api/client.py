from __future__ import absolute_import

import datetime
import json
import socket
import ssl
import uuid

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlsplit, urlencode
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urlparse import urlsplit
    from urllib import urlencode

from renderhive_houdini.api.config import normalize_config
from renderhive_houdini.api.errors import (
    ApiAuthenticationError,
    ApiConnectionError,
    ApiResponseError,
)
from renderhive_houdini.version import __version__


class RenderHiveApiClient(object):
    def __init__(self, config):
        self.config = normalize_config(config)

    @property
    def base_url(self):
        return self.config["base_url"]

    def _endpoint(self, name, **values):
        path = str(self.config.get("endpoints", {}).get(name) or "").strip()
        if not path:
            raise ApiResponseError("API endpoint is not configured: {}".format(name))
        try:
            path = path.format(**values)
        except KeyError as error:
            raise ApiResponseError("Missing endpoint placeholder {} for {}".format(error, name))
        if path.startswith(("http://", "https://")):
            return path
        return "{}/{}".format(self.base_url.rstrip("/"), path.lstrip("/"))

    def _headers(self, request_id, method):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RenderHive-Houdini/{}".format(__version__),
            "X-RenderHive-Request-ID": request_id,
        }
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            headers["X-RenderHive-Idempotency-Key"] = request_id
        auth = self.config.get("auth", {})
        token = str(auth.get("token") or "").strip()
        auth_type = str(auth.get("type") or "token").lower()
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
    def _decode(raw):
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
    def _error_message(payload, status):
        if isinstance(payload, dict):
            for key in ("detail", "message", "error", "non_field_errors"):
                value = payload.get(key)
                if value:
                    if isinstance(value, list):
                        value = "; ".join(str(item) for item in value)
                    return str(value)
            fields = []
            for key, value in payload.items():
                if value:
                    fields.append("{}: {}".format(key, value))
            if fields:
                return " | ".join(fields)
        return "RenderHive API returned HTTP {}.".format(status)

    def request_url(self, method, url, payload=None):
        method = str(method or "GET").upper()
        request_id = str(uuid.uuid4())
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers=self._headers(request_id, method))
        request.get_method = lambda: method
        try:
            response = urlopen(
                request,
                timeout=int(self.config.get("timeout_seconds", 15)),
                context=self._ssl_context(),
            )
            status = getattr(response, "status", None) or response.getcode()
            data = self._decode(response.read(10 * 1024 * 1024 + 1))
            return {
                "status_code": int(status),
                "data": data,
                "request_id": request_id,
                "url": url,
            }
        except HTTPError as error:
            payload_data = self._decode(error.read())
            message = self._error_message(payload_data, int(error.code))
            if int(error.code) in (401, 403):
                raise ApiAuthenticationError(message, status_code=int(error.code), payload=payload_data, url=url, request_id=request_id)
            raise ApiResponseError(message, status_code=int(error.code), payload=payload_data, url=url, request_id=request_id)
        except (URLError, socket.timeout) as error:
            reason = getattr(error, "reason", error)
            raise ApiConnectionError("Cannot connect to {}: {}".format(url, reason), url=url, request_id=request_id)

    def request(self, method, endpoint_name, payload=None, endpoint_values=None):
        return self.request_url(method, self._endpoint(endpoint_name, **(endpoint_values or {})), payload=payload)

    @staticmethod
    def _extract_list(payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("results", "items", "data", "workers", "pools", "jobs"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    def _list_all_pages(self, endpoint_name, max_pages=100):
        url = self._endpoint(endpoint_name)
        items = []
        visited = set()
        for _index in range(int(max_pages)):
            if not url or url in visited:
                break
            visited.add(url)
            response = self.request_url("GET", url)
            data = response.get("data", {})
            items.extend(self._extract_list(data))
            next_url = data.get("next") if isinstance(data, dict) else None
            if not next_url:
                break
            if str(next_url).startswith(("http://", "https://")):
                base = urlsplit(self.base_url)
                target = urlsplit(str(next_url))
                if (base.scheme, base.hostname, base.port) != (target.scheme, target.hostname, target.port):
                    raise ApiResponseError("Refusing cross-origin pagination URL.")
                url = str(next_url)
            else:
                url = "{}/{}".format(self.base_url.rstrip("/"), str(next_url).lstrip("/"))
        return items

    def test_connection(self):
        return self.request("GET", "connection_test").get("data", {})

    def list_workers(self):
        return self._list_all_pages("workers")

    def list_pools(self):
        return self._list_all_pages("pools")

    def get_worker(self, worker_id):
        return self.request(
            "GET",
            "worker_detail",
            endpoint_values={"worker_id": worker_id},
        ).get("data", {})

    def get_pool(self, pool_id):
        return self.request(
            "GET",
            "pool_detail",
            endpoint_values={"pool_id": pool_id},
        ).get("data", {})

    def list_jobs(self):
        return self._list_all_pages("jobs")

    @staticmethod
    def _parse_datetime(value):
        value = str(value or "").strip()
        if not value:
            return None
        try:
            return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    def submit_job(self, payload):
        response = self.request("POST", "jobs", payload=payload)
        data = response.get("data", {})
        if not isinstance(data, dict):
            data = {"message": str(data)}
        data.setdefault("_renderhive_request_id", response.get("request_id", ""))
        return data
