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


def validate(context, node_info=None, nodes=None, dependencies=None, farm_context=None):
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
    return results


def summary(results):
    counts = {"ERROR": 0, "WARNING": 0, "INFO": 0, "PASSED": 0, "total": 0}
    for item in results or []:
        severity = str(getattr(item, "severity", "INFO") or "INFO").upper()
        counts[severity] = counts.get(severity, 0) + 1
        counts["total"] += 1
    counts["valid"] = counts.get("ERROR", 0) == 0
    return counts
