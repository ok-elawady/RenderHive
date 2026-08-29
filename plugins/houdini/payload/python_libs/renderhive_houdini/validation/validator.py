"""Production validation orchestration for one or more Houdini render sources."""

from __future__ import absolute_import

from renderhive_houdini.validation import scene_checks, render_checks, dependency_checks, farm_checks
from renderhive_houdini.validation.result import ValidationResult


def _output_collision_results(nodes):
    owners = {}
    results = []
    for node in nodes or []:
        output = str(getattr(node, "output_path", "") or "").strip().lower()
        if not output:
            continue
        path = str(getattr(node, "path", "") or "")
        previous = owners.get(output)
        if previous and previous != path:
            results.append(ValidationResult(
                "ERROR", "Output",
                "Multiple selected render sources write to the same output path. Configure unique outputs before submitting.",
                path,
                code="MULTI_SOURCE_OUTPUT_COLLISION",
                data={"first_node": previous, "second_node": path, "output_path": output},
            ))
        else:
            owners[output] = path
    return results


KNOWN_HOUDINI_RULES = [
    ("SCENE_UNSAVED", "Scene File", "HIP file is saved to disk before submitting", "ERROR"),
    ("SCENE_DIRTY", "Scene File", "HIP file has no unsaved modifications", "WARNING"),
    ("PROJECT_INVALID", "Project", "A valid shared project path is configured", "ERROR"),
    ("JOB_UNSET", "Project", "$JOB variable is set for relative asset paths", "WARNING"),
    ("NO_RENDER_NODES_SELECTED", "Render Target", "At least one render source (ROP/Solaris) is selected", "ERROR"),
    ("NODE_INVALID", "Render Target", "Target render node exists in the scene", "ERROR"),
    ("FRAME_RANGE_INVALID", "Frame Range", "Frame start is less than or equal to frame end", "ERROR"),
    ("FRAME_STEP_INVALID", "Frame Range", "Frame step is a positive number", "ERROR"),
    ("CAMERA_UNSET", "Camera", "Render camera is assigned on the render node", "ERROR"),
    ("CAMERA_NON_RENDERABLE", "Camera", "Assigned camera exists and is valid", "ERROR"),
    ("OUTPUT_PATH_MISSING", "Output", "Output picture path is configured on render node", "ERROR"),
    ("OUTPUT_PATH_UNEXPANDED", "Output", "Output path contains valid frame padding ($F)", "WARNING"),
    ("MULTI_SOURCE_OUTPUT_COLLISION", "Output", "Multiple render sources do not write to identical output paths", "ERROR"),
    ("DEPENDENCY_MISSING", "Dependencies", "Referenced external textures, geometry, and VDBs exist on disk", "ERROR"),
    ("FARM_CHUNK_SIZE_INVALID", "Farm Targeting", "Task chunk size is greater than zero", "ERROR"),
    ("FARM_NO_ELIGIBLE_WORKERS", "Farm Targeting", "Target worker pools contain eligible workers", "WARNING"),
]

RULE_PROFILES = {
    "standard": {
        "name": "Standard (Default)",
        "description": "Standard studio baseline",
        "overrides": {},
    },
    "studio_strict": {
        "name": "Studio Strict",
        "description": "Enforces zero warnings; all checks must strictly pass",
        "overrides": {
            "SCENE_DIRTY": "ERROR",
            "JOB_UNSET": "ERROR",
            "OUTPUT_PATH_UNEXPANDED": "ERROR",
            "FARM_NO_ELIGIBLE_WORKERS": "ERROR",
        },
    },
    "lookdev": {
        "name": "LookDev / Relaxed",
        "description": "Allows fast test turns with advisory warnings",
        "overrides": {
            "SCENE_DIRTY": "INFO",
            "JOB_UNSET": "INFO",
            "DEPENDENCY_MISSING": "WARNING",
            "FARM_NO_ELIGIBLE_WORKERS": "INFO",
        },
    },
}


def apply_rule_overrides(results, overrides):
    """Applies user or studio severity overrides and filters out disabled rules."""
    if not overrides:
        return results
    filtered = []
    for res in results:
        code = getattr(res, "code", None)
        if code and code in overrides:
            override_val = str(overrides[code] or "").upper()
            if override_val in ("DISABLED", "IGNORE", "OFF", "SKIP"):
                continue
            if override_val in ("ERROR", "WARNING", "INFO", "PASSED"):
                res.severity = override_val
        filtered.append(res)
    return filtered


def validate(context, node_info=None, nodes=None, dependencies=None, farm_context=None, rule_overrides=None):
    results = []
    results.extend(scene_checks.run(context))
    selected_nodes = list(nodes or [])
    if not selected_nodes and node_info is not None:
        selected_nodes = [node_info]
    if not selected_nodes:
        results.extend(render_checks.run(None))
    else:
        seen = set()
        for node in selected_nodes:
            path = str(getattr(node, "path", "") or "")
            if path and path in seen:
                continue
            if path:
                seen.add(path)
            results.extend(render_checks.run(node))
        results.extend(_output_collision_results(selected_nodes))
    if dependencies is not None:
        results.extend(dependency_checks.run(dependencies, getattr(context, "project_path", "") if context else ""))
    if farm_context is not None:
        data = dict(farm_context or {})
        data["render_nodes"] = selected_nodes
        results.extend(farm_checks.run(context, selected_nodes[0] if selected_nodes else None, data))
    if rule_overrides:
        results = apply_rule_overrides(results, rule_overrides)
    return results


def summary(results):
    counts = {"ERROR": 0, "WARNING": 0, "INFO": 0, "PASSED": 0, "total": 0}
    for item in results or []:
        severity = str(getattr(item, "severity", "INFO") or "INFO").upper()
        counts[severity] = counts.get(severity, 0) + 1
        counts["total"] += 1
    counts["valid"] = counts.get("ERROR", 0) == 0
    return counts
