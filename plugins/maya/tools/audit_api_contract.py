from __future__ import print_function

import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

try:
    import jsonschema
except ImportError:
    jsonschema = None


TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TOOL_DIR)
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from api.config import DEFAULT_CONFIG
from api.contract import SUBMITTER_ENDPOINTS, WORKER_OWNED_ENDPOINTS
from api.payload import build_job_request


METHODS = ("get", "post", "put", "patch", "delete")


def canonical_path(path):
    path = str(path or "").split("?", 1)[0]
    path = re.sub(r"\{[^}]+\}", "{}", path)
    if not path.startswith("/"):
        path = "/" + path
    return path


def method_set(operation):
    if "methods" in operation:
        return set(str(value).upper() for value in operation["methods"])
    return {str(operation.get("method") or "GET").upper()}


def dummy_task():
    return {
        "project_name": "ContractTest",
        "job_name": "MayaContractTest",
        "department": "Lighting",
        "priority": 50,
        "scene_path": "C:/RenderHive/scenes/test.ma",
        "project_path": "C:/RenderHive",
        "output_path": "C:/RenderHive/images",
        "renderer": "arnold",
        "camera": "renderCam",
        "image_name": "beauty",
        "image_format": "exr",
        "frame_padding": 4,
        "width": 1920,
        "height": 1080,
        "frame_start": 1,
        "frame_end": 10,
        "frame_step": 1,
        "chunk_size": 2,
        "retry_count": 2,
        "task_timeout_minutes": 60,
        "concurrent_tasks": 1,
        "effective_pool_ids": [],
        "effective_pool_names": [],
        "submission_mode": "Shared Storage",
        "software_info": {"maya_version": "2023"},
        "validation": {},
    }


def audit(spec):
    paths = spec.get("paths") or {}
    configured = DEFAULT_CONFIG.get("endpoints") or {}
    checks = []

    for name, definition in sorted(SUBMITTER_ENDPOINTS.items()):
        configured_path = configured.get(name)
        expected_path = definition.get("path")
        path_match = (
            canonical_path(configured_path)
            == canonical_path(expected_path)
        )
        spec_path = None
        for candidate in paths:
            if canonical_path(candidate) == canonical_path(expected_path):
                spec_path = candidate
                break

        available_methods = set()
        if spec_path:
            available_methods = {
                method.upper()
                for method in paths[spec_path]
                if method.lower() in METHODS
            }

        required_methods = method_set(definition)
        checks.append({
            "endpoint": name,
            "configured_path": configured_path,
            "openapi_path": spec_path,
            "path_match": path_match,
            "required_methods": sorted(required_methods),
            "available_methods": sorted(available_methods),
            "method_match": required_methods.issubset(available_methods),
            "ok": bool(
                configured_path
                and spec_path
                and path_match
                and required_methods.issubset(available_methods)
            ),
        })

    schemas = spec.get("components", {}).get("schemas", {})
    job_create = schemas.get("JobCreate") or {}
    layer_create = schemas.get("LayerCreate") or {}
    job_fields = set((job_create.get("properties") or {}).keys())
    layer_fields = set((layer_create.get("properties") or {}).keys())

    post_job = paths.get("/api/jobs/", {}).get("post", {})
    response_201 = (
        post_job.get("responses", {})
        .get("201", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    response_ref = str(response_201.get("$ref") or "")

    gaps = []
    if response_ref.endswith("/JobCreate"):
        gaps.append({
            "id": "job_create_response_reference",
            "severity": "required_backend_change",
            "message": (
                "POST /api/jobs/ returns JobCreate, which has no id/state. "
                "Return JobDetail or a response containing id, state and created_at."
            ),
        })

    if not any(name in layer_fields for name in ("target_pool_ids", "pool_ids")):
        gaps.append({
            "id": "pool_targeting_not_persisted",
            "severity": "required_backend_change",
            "message": (
                "LayerCreate has no target pool field. Maya can read pools and "
                "send metadata, but the API contract cannot guarantee pool-based dispatch."
            ),
        })

    for field, message in (
        (
            "start_suspended",
            "JobCreate has no atomic start_suspended field; Maya currently submits then pauses.",
        ),
        (
            "machine_limit",
            "JobCreate has no machine_limit field; that UI value is metadata only.",
        ),
        (
            "dependencies",
            "JobCreate has no job dependency field; dependency text is metadata only.",
        ),
    ):
        if field not in job_fields:
            gaps.append({
                "id": "missing_{}".format(field),
                "severity": "optional_backend_change",
                "message": message,
            })

    payload_result = {
        "built": False,
        "schema_valid": None,
        "error": "",
    }
    try:
        payload = build_job_request(dummy_task(), DEFAULT_CONFIG)
        payload_result["built"] = True
        if jsonschema is not None:
            resolver = jsonschema.RefResolver.from_schema(spec)
            jsonschema.validate(
                payload,
                job_create,
                resolver=resolver,
            )
            payload_result["schema_valid"] = True
        else:
            payload_result["schema_valid"] = "not_checked_jsonschema_missing"
    except Exception as error:
        payload_result["schema_valid"] = False
        payload_result["error"] = str(error)

    security_schemes = (
        spec.get("components", {})
        .get("securitySchemes", {})
    )

    return {
        "api": spec.get("info") or {},
        "endpoint_checks": checks,
        "all_submitter_endpoints_valid": all(item["ok"] for item in checks),
        "payload": payload_result,
        "security": {
            "token_auth_present": "tokenAuth" in security_schemes,
            "x_session_token_present": "XSessionTokenAuth" in security_schemes,
        },
        "worker_owned_endpoints": sorted(WORKER_OWNED_ENDPOINTS),
        "backend_gaps": gaps,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Audit RenderHive Maya against an OpenAPI YAML file."
    )
    parser.add_argument("openapi", help="Path to RenderHive OpenAPI YAML")
    parser.add_argument("--json", dest="json_path", help="Optional output JSON path")
    args = parser.parse_args()

    if yaml is None:
        raise RuntimeError("PyYAML is required to run this development audit.")

    with open(args.openapi, "r", encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)

    result = audit(spec)
    print(json.dumps(result, indent=2, sort_keys=False))

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=False)

    return 0 if (
        result["all_submitter_endpoints_valid"]
        and result["payload"].get("schema_valid") is not False
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
