from __future__ import absolute_import

import datetime
import json
import socket
import ssl
import time
import uuid

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlsplit
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urlparse import urlsplit

from .config import normalize_config
from .errors import (
    ApiAuthenticationError,
    ApiConnectionError,
    ApiHttpError,
    ApiNotFoundError,
    ApiRateLimitError,
    ApiResponseError,
)
from .version import USER_AGENT
from core.runtime_log import get_logger


LOGGER = get_logger("api")
_TRANSIENT_HTTP_CODES = {429, 502, 503, 504}


class RenderHiveApiClient(object):
    def __init__(self, config):
        self.config = normalize_config(config)

    @property
    def base_url(self):
        return self.config["base_url"]

    @property
    def timeout(self):
        return int(self.config.get("timeout_seconds", 15))

    @property
    def network(self):
        return self.config.get("network", {})

    def _endpoint(self, name, **values):
        path = self.config.get("endpoints", {}).get(name)
        if not path:
            raise ApiResponseError("API endpoint is not configured: {}".format(name))
        try:
            path = str(path).format(**values)
        except KeyError as error:
            raise ApiResponseError("Missing endpoint value {} for {}".format(error, name))
        if path.startswith(("http://", "https://")):
            self._assert_safe_url(path, source="endpoint '{}'".format(name))
            return path
        return "{}/{}".format(self.base_url.rstrip("/"), path.lstrip("/"))

    @staticmethod
    def _origin(url):
        parsed = urlsplit(str(url or ""))
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80
        return (parsed.scheme.lower(), (parsed.hostname or "").lower(), int(port))

    def _assert_safe_url(self, url, source="request"):
        parsed = urlsplit(str(url or ""))
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ApiResponseError("Invalid {} URL: {}".format(source, url))
        if parsed.username or parsed.password:
            raise ApiResponseError("Credentials are not allowed inside API URLs.")
        if (
            self._origin(url) != self._origin(self.base_url)
            and not bool(self.network.get("allow_cross_origin_pagination", False))
        ):
            raise ApiResponseError(
                "Refusing cross-origin {} URL to protect API credentials: {}".format(
                    source, url
                )
            )
        return str(url)

    def _headers(self, request_id=None, method="GET"):
        request_id = str(request_id or uuid.uuid4())
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-RenderHive-Request-ID": request_id,
        }
        if str(method or "GET").upper() in ("POST", "PUT", "PATCH", "DELETE"):
            headers["X-RenderHive-Idempotency-Key"] = request_id

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

    def _read_response(self, response):
        limit = int(self.network.get("max_response_bytes", 10 * 1024 * 1024))
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ApiResponseError(
                "API response exceeded the configured {} byte limit.".format(limit)
            )
        return self._decode_response(raw)

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

    @staticmethod
    def _http_error_class(status_code):
        status_code = int(status_code)
        if status_code in (401, 403): return ApiAuthenticationError
        if status_code == 404: return ApiNotFoundError
        if status_code == 429: return ApiRateLimitError
        return ApiHttpError

    @staticmethod
    def _retry_after(headers):
        try:
            value = headers.get("Retry-After")
            return max(0.0, float(value)) if value is not None else None
        except Exception:
            return None

    def _retry_delay(self, attempt, retry_after=None):
        cap = float(self.network.get("max_retry_delay_seconds", 5.0))
        if retry_after is not None:
            return min(cap, max(0.0, float(retry_after)))
        base = float(self.network.get("retry_backoff_seconds", 0.4))
        return min(cap, base * (2 ** int(attempt)))

    def _request_url(self, method, url, payload=None, request_id=None, retry_attempts=None):
        method = str(method or "GET").upper()
        request_id = str(request_id or uuid.uuid4())
        url = self._assert_safe_url(url)
        body = None
        if payload is not None:
            try:
                body = json.dumps(payload).encode("utf-8")
            except Exception as error:
                raise ApiResponseError(
                    "Could not serialize API request body: {}".format(error),
                    url=url,
                    request_id=request_id,
                )

        if retry_attempts is None:
            retry_attempts = int(self.network.get("get_retry_attempts", 2)) if method == "GET" else 0

        last_error = None
        LOGGER.info("%s %s request_id=%s", method, url, request_id)
        for attempt in range(int(retry_attempts) + 1):
            request = Request(
                url,
                data=body,
                headers=self._headers(request_id=request_id, method=method),
            )
            request.get_method = lambda: method
            response = None
            try:
                response = urlopen(
                    request,
                    timeout=self.timeout,
                    context=self._ssl_context(),
                )
                status_code = getattr(response, "status", None) or response.getcode()
                data = self._read_response(response)
                headers = dict(getattr(response, "headers", {}) or {})
                LOGGER.info("%s %s -> %s request_id=%s", method, url, status_code, request_id)
                return {
                    "ok": 200 <= int(status_code) < 300,
                    "status_code": int(status_code),
                    "data": data,
                    "url": url,
                    "request_id": request_id,
                    "response_headers": headers,
                }
            except HTTPError as error:
                try:
                    payload_data = self._decode_response(error.read())
                except Exception:
                    payload_data = {}
                status_code = int(error.code)
                headers = getattr(error, "headers", {}) or {}
                retry_after = self._retry_after(headers)
                error_class = self._http_error_class(status_code)
                last_error = error_class(
                    status_code,
                    self._error_message(payload_data, status_code),
                    payload=payload_data,
                    url=url,
                    request_id=request_id,
                    retry_after=retry_after,
                )
                LOGGER.warning("%s %s -> %s request_id=%s", method, url, status_code, request_id)
                if method == "GET" and status_code in _TRANSIENT_HTTP_CODES and attempt < int(retry_attempts):
                    time.sleep(self._retry_delay(attempt, retry_after))
                    continue
                raise last_error
            except (URLError, socket.timeout) as error:
                reason = getattr(error, "reason", error)
                last_error = ApiConnectionError(
                    "Cannot connect to {}: {}".format(url, reason),
                    url=url,
                    request_id=request_id,
                )
                if method == "GET" and attempt < int(retry_attempts):
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise last_error
            except ApiResponseError:
                raise
            except Exception as error:
                last_error = ApiConnectionError(
                    "RenderHive API request failed: {}".format(error),
                    url=url,
                    request_id=request_id,
                )
                if method == "GET" and attempt < int(retry_attempts):
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise last_error
            finally:
                try:
                    if response is not None:
                        response.close()
                except Exception:
                    pass

        if last_error is not None:
            raise last_error
        raise ApiConnectionError(
            "RenderHive API request failed without a response.",
            url=url,
            request_id=request_id,
        )

    def request(self, method, endpoint_name, payload=None, endpoint_values=None, request_id=None):
        url = self._endpoint(endpoint_name, **(endpoint_values or {}))
        return self._request_url(method, url, payload=payload, request_id=request_id)

    def test_connection(self):
        return self.request("GET", "connection_test")

    @staticmethod
    def _extract_list(payload, keys=("results", "items", "data")):
        if isinstance(payload, list): return payload
        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if isinstance(value, list): return value
        return []

    def _list_all_pages(self, endpoint_name, list_keys, max_pages=100, endpoint_values=None):
        url = self._endpoint(endpoint_name, **(endpoint_values or {}))
        items, visited, page_count = [], set(), 0
        while url and url not in visited:
            page_count += 1
            if page_count > int(max_pages):
                raise ApiResponseError(
                    "Pagination exceeded {} pages for {}.".format(max_pages, endpoint_name)
                )
            url = self._assert_safe_url(url, source="pagination")
            visited.add(url)
            response = self._request_url("GET", url)
            payload = response.get("data", {})
            items.extend(self._extract_list(payload, keys=list_keys))
            next_url = payload.get("next") if isinstance(payload, dict) else None
            if next_url and not str(next_url).startswith(("http://", "https://")):
                next_url = "{}/{}".format(self.base_url.rstrip("/"), str(next_url).lstrip("/"))
            url = next_url
        if url in visited:
            LOGGER.warning("Pagination loop stopped for %s", endpoint_name)
        return items

    def list_jobs(self): return self.request("GET", "jobs").get("data", {})
    def list_all_jobs(self): return self._list_all_pages("jobs", ("results", "jobs", "items", "data"))
    def list_workers(self): return self._list_all_pages("workers", ("results", "workers", "items", "data"))
    def get_worker(self, worker_id): return self.request("GET", "worker_detail", endpoint_values={"worker_id": worker_id}).get("data", {})
    def list_pools(self): return self._list_all_pages("pools", ("results", "pools", "items", "data"))
    def get_pool(self, pool_id): return self.request("GET", "pool_detail", endpoint_values={"pool_id": pool_id}).get("data", {})

    @staticmethod
    def _parse_datetime(value):
        value = str(value or "").strip()
        if not value: return None
        if value.endswith("Z"): value = value[:-1] + "+00:00"
        try: parsed = datetime.datetime.fromisoformat(value)
        except Exception: return None
        if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.astimezone(datetime.timezone.utc)

    def _resolve_created_job(self, submitted_payload, submitted_after=None):
        jobs = self.list_all_jobs()
        visible_name = str(submitted_payload.get("visible_name") or "").strip()
        project = str(submitted_payload.get("project") or "").strip()
        user = str(submitted_payload.get("user") or "").strip()
        if submitted_after is not None:
            submitted_after = submitted_after.astimezone(datetime.timezone.utc) - datetime.timedelta(seconds=10)
        candidates = []
        for job in jobs:
            if not isinstance(job, dict): continue
            if visible_name and str(job.get("visible_name") or "") != visible_name: continue
            if project and str(job.get("project") or "") != project: continue
            if user and str(job.get("user") or "") != user: continue
            created_at = self._parse_datetime(job.get("created_at"))
            if submitted_after is not None and created_at is not None and created_at < submitted_after: continue
            candidates.append(job)
        if not candidates: return {}
        candidates.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return dict(candidates[0])

    def submit_job(self, payload):
        submitted_at = datetime.datetime.now(datetime.timezone.utc)
        request_id = str(uuid.uuid4())
        response = self.request("POST", "jobs", payload=payload, request_id=request_id)
        data = response.get("data", {})
        if not isinstance(data, dict):
            raise ApiResponseError(
                "Job submission response must be a JSON object.",
                url=response.get("url", ""),
                request_id=request_id,
            )
        job_id = data.get("id") or data.get("job_id") or data.get("uid")
        if not job_id:
            resolved = self._resolve_created_job(payload, submitted_after=submitted_at)
            if resolved:
                merged = dict(data); merged.update(resolved); merged["_renderhive_resolved_from_list"] = True; data = merged
            else:
                data = dict(data); data["_renderhive_missing_job_reference"] = True
        data.setdefault("_renderhive_request_id", response.get("request_id", request_id))
        return data

    def get_job_status(self, job_id): return self.request("GET", "job_status", endpoint_values={"job_id": job_id}).get("data", {})

    def update_job(self, job_id, visible_name=None, priority=None, max_frames_per_worker=None):
        payload = {}
        if visible_name is not None: payload["visible_name"] = str(visible_name).strip()
        if priority is not None: payload["priority"] = int(priority)
        if max_frames_per_worker is not None: payload["max_frames_per_worker"] = int(max_frames_per_worker)
        if not payload: raise ApiResponseError("At least one job field is required for update.")
        return self.request("PATCH", "job_update", payload=payload, endpoint_values={"job_id": job_id}).get("data", {})

    def pause_job(self, job_id): return self.request("POST", "job_pause", endpoint_values={"job_id": job_id}).get("data", {})
    def resume_job(self, job_id): return self.request("POST", "job_resume", endpoint_values={"job_id": job_id}).get("data", {})
    def delete_job(self, job_id): return self.request("DELETE", "job_delete", endpoint_values={"job_id": job_id})
    def list_job_layers(self, job_id): return self._list_all_pages("job_layers", ("results", "layers", "items", "data"), endpoint_values={"job_id": job_id})
    def get_job_layer(self, job_id, layer_id): return self.request("GET", "job_layer_detail", endpoint_values={"job_id": job_id, "layer_id": layer_id}).get("data", {})
    def list_layer_frames(self, job_id, layer_id): return self._list_all_pages("job_layer_frames", ("results", "frames", "items", "data"), endpoint_values={"job_id": job_id, "layer_id": layer_id})
    def get_layer_frame(self, job_id, layer_id, frame_id): return self.request("GET", "job_layer_frame_detail", endpoint_values={"job_id": job_id, "layer_id": layer_id, "frame_id": frame_id}).get("data", {})
