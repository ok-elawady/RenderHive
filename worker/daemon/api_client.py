"""RenderHive backend REST API client with robust timeouts and headers."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import requests

from core.ui_helpers import select_worker_record
from version import WORKER_VERSION


class RenderHiveApiClient:
    """Encapsulates all HTTP communication with the RenderHive backend API."""

    def __init__(self, api_url: str, api_token: str):
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.session = requests.Session()

    def get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": "Token {}".format(self.api_token),
            "Content-Type": "application/json",
            "User-Agent": "RenderHive-Worker/{}".format(WORKER_VERSION),
        }

    def ping(self, payload: Dict[str, Any], timeout: float = 8.0) -> requests.Response:
        return self.session.post(
            "{}/workers/ping/".format(self.api_url),
            json=payload,
            headers=self.get_headers(),
            timeout=timeout,
        )

    def dispatch(
        self,
        worker_name: str,
        tags: List[str],
        capabilities: Dict[str, Any],
        capabilities_snapshot: Dict[str, Any],
        timeout: float = 15.0,
    ) -> requests.Response:
        return self.session.post(
            "{}/tasks/dispatch/".format(self.api_url),
            json={
                "worker_name": worker_name,
                "tags": tags,
                "capabilities": capabilities,
                "capabilities_snapshot": capabilities_snapshot,
            },
            headers=self.get_headers(),
            timeout=timeout,
        )

    def fetch_worker_record(self, hostname: str, timeout: float = 8.0) -> Optional[Dict[str, Any]]:
        try:
            response = self.session.get(
                "{}/workers/".format(self.api_url),
                params={"search": hostname},
                headers=self.get_headers(),
                timeout=timeout,
            )
            if 200 <= response.status_code < 300:
                record = select_worker_record(response.json(), hostname)
                return record if record else None
        except Exception:
            pass
        return None

    def fetch_job_detail(self, job_id: str, timeout: float = 8.0) -> Dict[str, Any]:
        if not job_id:
            return {}
        try:
            response = self.session.get(
                "{}/jobs/{}/".format(self.api_url, job_id),
                headers=self.get_headers(),
                timeout=timeout,
            )
            if 200 <= response.status_code < 300:
                data = response.json()
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def report_task_status(
        self,
        task_id: str,
        exit_status: int,
        log_path: str = "",
        error_tail: str = "",
        duration_seconds: float = 0.0,
        output_image_path: str = "",
        worker_hostname: str = "",
        max_memory_used_mb: int = 0,
        timeout: float = 15.0,
    ) -> requests.Response:
        endpoint = "succeed" if exit_status == 0 else "fail"
        log_text = ""
        if log_path and os.path.isfile(log_path):
            try:
                file_size = os.path.getsize(log_path)
                max_read_bytes = 2 * 1024 * 1024  # 2 MB ceiling
                with open(log_path, "rb") as handle:
                    if file_size > max_read_bytes:
                        handle.seek(file_size - max_read_bytes)
                    log_bytes = handle.read()
                log_text = log_bytes.decode("utf-8", errors="replace")
            except Exception:
                pass

        payload: Dict[str, Any] = {
            "exit_status": int(exit_status),
            "worker_hostname": worker_hostname,
            "log_output": log_text,
            "error_tail": error_tail or "",
            "duration_seconds": duration_seconds,
            "output_image_path": output_image_path or "",
            "max_memory_used_mb": max(0, int(max_memory_used_mb or 0)),
        }

        return self.session.post(
            "{}/tasks/{}/{}/".format(self.api_url, task_id, endpoint),
            json=payload,
            headers=self.get_headers(),
            timeout=timeout,
        )
