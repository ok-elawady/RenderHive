from __future__ import print_function

import argparse
import json
import os
import re
import sys

import jsonschema
import yaml

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TOOL_DIR)
LIB_ROOT = os.path.join(PLUGIN_ROOT, "payload", "python_libs")
if LIB_ROOT not in sys.path:
    sys.path.insert(0, LIB_ROOT)

from renderhive_houdini.adapters.render_node_registry import RenderNodeInfo
from renderhive_houdini.api.config import DEFAULT_CONFIG
from renderhive_houdini.api.contract import SUBMITTER_ENDPOINTS, WORKER_OWNED_ENDPOINTS
from renderhive_houdini.api.endpoints import DEFAULT_ENDPOINTS
from renderhive_houdini.core.scene_context import SceneContext
from renderhive_houdini.core.task_builder import build_api_request, build_task

METHODS = {"get", "post", "put", "patch", "delete"}


def canonical_path(path):
    path = str(path or "").split("?", 1)[0]
    return re.sub(r"\{[^}]+\}", "{}", path)


def matching_spec_path(paths, expected):
    expected = canonical_path(expected)
    return next((candidate for candidate in paths if canonical_path(candidate) == expected), None)


def dummy_payload():
    context = SceneContext(
        hip_path="C:/RenderHive/scenes/test.hip", hip_name="test.hip",
        houdini_version="20.5.278", frame_start=1, frame_end=10,
        current_frame=1, fps=24, hip_directory="C:/RenderHive/scenes",
        job_directory="C:/RenderHive", is_new_file=False,
        has_unsaved_changes=False, scene_name="test", project_name="RenderHive",
        project_path="C:/RenderHive", output_root="C:/RenderHive/render",
    )
    node = RenderNodeInfo(
        path="/stage/usdrender1", name="beauty", type_name="usdrender_rop",
        type_label="USD Render ROP", category="Driver", renderer="Karma XPU",
        execution_mode="husk", frame_start=1, frame_end=10, frame_step=1,
        frame_source="Render Node", camera="/stage/cam1",
        output_path="C:/RenderHive/render/beauty.$F4.exr",
        resolution_width=1920, resolution_height=1080,
        is_bypassed=False, is_locked=False, is_renderable=True,
        usd_output_path="C:/RenderHive/usd/scene.usd",
    )
    task = build_task(
        context, node, "HoudiniContractTest", "RenderHive", chunk_size=2,
        concurrent_tasks=1, render_nodes=[node], min_cores=8,
        min_memory_mb=16384, min_gpus=1,
        pool_targeting={
            "strategy": "selected_only",
            "selected_pool_ids": ["11111111-1111-4111-8111-111111111111"],
            "effective_pool_ids": ["11111111-1111-4111-8111-111111111111"],
            "effective_pool_names": ["Houdini"],
        },
        dependencies=["22222222-2222-4222-8222-222222222222"],
    )
    return build_api_request(task, DEFAULT_CONFIG)


def audit(spec):
    paths = spec.get("paths") or {}
    endpoint_checks = []
    for name, definition in sorted(SUBMITTER_ENDPOINTS.items()):
        configured = DEFAULT_ENDPOINTS.get(name)
        expected = definition.get("path")
        spec_path = matching_spec_path(paths, expected)
        required = {str(value).upper() for value in definition.get("methods", (definition.get("method", "GET"),))}
        available = {m.upper() for m in (paths.get(spec_path) or {}) if m.lower() in METHODS} if spec_path else set()
        endpoint_checks.append({
            "endpoint": name,
            "configured_path": configured,
            "openapi_path": spec_path,
            "required_methods": sorted(required),
            "available_methods": sorted(available),
            "ok": bool(configured and canonical_path(configured) == canonical_path(expected) and spec_path and required.issubset(available)),
        })

    worker_checks = []
    for expected, method in sorted(WORKER_OWNED_ENDPOINTS.items()):
        spec_path = matching_spec_path(paths, expected)
        worker_checks.append({
            "path": expected,
            "method": method,
            "openapi_path": spec_path,
            "ok": bool(spec_path and method.lower() in paths[spec_path]),
        })

    payload = dummy_payload()
    schema = {"$ref": "#/components/schemas/JobCreate", "components": spec.get("components", {})}
    jsonschema.validate(payload, schema, format_checker=jsonschema.FormatChecker())

    security = spec.get("components", {}).get("securitySchemes", {})
    response_schema = (((paths.get("/api/jobs/") or {}).get("post") or {}).get("responses") or {}).get("201", {})
    response_ref = (((response_schema.get("content") or {}).get("application/json") or {}).get("schema") or {}).get("$ref", "")
    backend_notes = []
    if str(response_ref).endswith("/JobCreate"):
        backend_notes.append(
            "POST /api/jobs/ is documented as JobCreate, so submitters may need the task_uid lookup fallback when id/state are absent."
        )

    return {
        "api": spec.get("info") or {},
        "submitter_endpoints": endpoint_checks,
        "worker_endpoints": worker_checks,
        "all_submitter_endpoints_valid": all(item["ok"] for item in endpoint_checks),
        "all_worker_endpoints_valid": all(item["ok"] for item in worker_checks),
        "payload_schema_valid": True,
        "payload_layer_count": len(payload.get("layers") or []),
        "native_pool_targeting": bool(payload.get("included_pools")),
        "job_dependencies": bool(payload.get("dependencies")),
        "token_auth": "tokenAuth" in security,
        "x_session_token_auth": "XSessionTokenAuth" in security,
        "backend_notes": backend_notes,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit RenderHive Houdini against API 0.2.0 OpenAPI YAML.")
    parser.add_argument("openapi")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    with open(args.openapi, "r", encoding="utf-8") as handle:
        result = audit(yaml.safe_load(handle))
    print(json.dumps(result, indent=2))
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    ok = (
        result["all_submitter_endpoints_valid"]
        and result["all_worker_endpoints_valid"]
        and result["payload_schema_valid"]
        and result["native_pool_targeting"]
        and result["job_dependencies"]
        and result["token_auth"]
        and result["x_session_token_auth"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
