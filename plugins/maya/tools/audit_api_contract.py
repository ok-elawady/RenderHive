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


def _matching_spec_path(paths, expected_path):
    expected = canonical_path(expected_path)
    for candidate in paths:
        if canonical_path(candidate) == expected:
            return candidate
    return None


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
        "pool_strategy": "selected",
        "selected_pool_ids": ["11111111-1111-1111-1111-111111111111"],
        "selected_pool_names": ["GPU"],
        "excluded_pool_ids": [],
        "effective_pool_ids": ["11111111-1111-1111-1111-111111111111"],
        "effective_pool_names": ["GPU"],
        "job_dependencies": ["22222222-2222-2222-2222-222222222222"],
        "submission_mode": "Shared Storage",
        "software_info": {"maya_version": "2023"},
        "validation": {},
    }


def _endpoint_checks(paths, configured):
    checks = []
    for name, definition in sorted(SUBMITTER_ENDPOINTS.items()):
        configured_path = configured.get(name)
        expected_path = definition.get("path")
        path_match = canonical_path(configured_path) == canonical_path(expected_path)
        spec_path = _matching_spec_path(paths, expected_path)
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
    return checks


def _worker_endpoint_checks(paths):
    checks = []
    for expected_path, method in sorted(WORKER_OWNED_ENDPOINTS.items()):
        spec_path = _matching_spec_path(paths, expected_path)
        available_methods = set()
        if spec_path:
            available_methods = {
                name.upper()
                for name in paths[spec_path]
                if name.lower() in METHODS
            }
        checks.append({
            "expected_path": expected_path,
            "openapi_path": spec_path,
            "required_method": method,
            "available_methods": sorted(available_methods),
            "ok": bool(spec_path and method in available_methods),
        })
    return checks


def audit(spec):
    paths = spec.get("paths") or {}
    configured = DEFAULT_CONFIG.get("endpoints") or {}
    checks = _endpoint_checks(paths, configured)
    worker_checks = _worker_endpoint_checks(paths)

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
            "severity": "backend_recommended",
            "message": (
                "POST /api/jobs/ is documented as returning JobCreate, so the "
                "response has no id/state. The Maya plugin has a deterministic "
                "task_uid lookup fallback, but JobDetail is the cleaner production contract."
            ),
        })

    pool_fields_ok = {"included_pools", "excluded_pools"}.issubset(job_fields)
    if not pool_fields_ok:
        gaps.append({
            "id": "job_pool_targeting_missing",
            "severity": "blocking",
            "message": (
                "JobCreate must expose included_pools and excluded_pools for "
                "enforceable Maya pool targeting."
            ),
        })

    dependencies_ok = "dependencies" in job_fields
    if not dependencies_ok:
        gaps.append({
            "id": "job_dependencies_missing",
            "severity": "blocking",
            "message": "JobCreate must expose dependencies for Maya Job dependencies.",
        })

    payload_result = {
        "built": False,
        "schema_valid": None,
        "pool_targeting": False,
        "dependencies": False,
        "pool_names_used_as_tags": None,
        "error": "",
    }
    try:
        payload = build_job_request(dummy_task(), DEFAULT_CONFIG)
        payload_result["built"] = True
        payload_result["pool_targeting"] = payload.get("included_pools") == [
            "11111111-1111-1111-1111-111111111111"
        ] and payload.get("excluded_pools") == []
        payload_result["dependencies"] = payload.get("dependencies") == [{
            "type": "JOB_ON_JOB",
            "parent_job": "22222222-2222-2222-2222-222222222222",
        }]
        payload_result["pool_names_used_as_tags"] = "GPU" in (
            payload.get("layers", [{}])[0].get("tags") or []
        )
        if jsonschema is not None:
            validation_schema = {
                "$ref": "#/components/schemas/JobCreate",
                "components": spec.get("components", {}),
            }
            jsonschema.validate(payload, validation_schema)
            payload_result["schema_valid"] = True
        else:
            payload_result["schema_valid"] = "not_checked_jsonschema_missing"
    except Exception as error:
        payload_result["schema_valid"] = False
        payload_result["error"] = str(error)

    security_schemes = spec.get("components", {}).get("securitySchemes", {})

    return {
        "api": spec.get("info") or {},
        "endpoint_checks": checks,
        "all_submitter_endpoints_valid": all(item["ok"] for item in checks),
        "worker_endpoint_checks": worker_checks,
        "all_worker_endpoints_valid": all(item["ok"] for item in worker_checks),
        "payload": payload_result,
        "contract_features": {
            "job_pool_targeting": pool_fields_ok,
            "job_dependencies": dependencies_ok,
            "layer_execution_mode": "execution_mode" in layer_fields,
            "max_frames_per_worker": "max_frames_per_worker" in job_fields,
        },
        "security": {
            "token_auth_present": "tokenAuth" in security_schemes,
            "x_session_token_present": "XSessionTokenAuth" in security_schemes,
        },
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

    ok = (
        result["all_submitter_endpoints_valid"]
        and result["all_worker_endpoints_valid"]
        and result["payload"].get("schema_valid") is not False
        and result["payload"].get("pool_targeting")
        and result["payload"].get("dependencies")
        and not result["payload"].get("pool_names_used_as_tags")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
