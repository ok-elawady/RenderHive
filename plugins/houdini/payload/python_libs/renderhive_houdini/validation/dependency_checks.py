"""External file validation for textures, caches, USD layers and HDAs."""

from __future__ import absolute_import

import os
import re

from renderhive_houdini.validation.result import ValidationResult

_LOCAL_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


def run(dependencies, project_path=""):
    values = list(dependencies or [])
    results = []
    if not values:
        return [ValidationResult("INFO", "Dependencies", "No external file references were reported by Houdini.", code="DEPENDENCIES_EMPTY")]

    missing = [item for item in values if not item.get("exists")]
    for item in missing:
        results.append(ValidationResult(
            "ERROR", "Dependencies", "Missing {}: {}".format(item.get("type") or "file", item.get("raw_path") or item.get("resolved_path")),
            item.get("node") or "", code="DEPENDENCY_MISSING",
            data=dict(item),
        ))

    local_paths = []
    for item in values:
        path = str(item.get("resolved_path") or "")
        if path and _LOCAL_DRIVE.match(path) and not str(item.get("raw_path") or "").startswith(("$HIP", "$JOB")):
            local_paths.append(item)
    for item in local_paths:
        results.append(ValidationResult(
            "WARNING", "Farm Paths", "Local absolute path may not be available to other workers: {}".format(item.get("resolved_path")),
            item.get("node") or "", code="DEPENDENCY_LOCAL_PATH", data=dict(item),
        ))

    if not missing:
        results.append(ValidationResult("PASSED", "Dependencies", "All {} external dependency references were found.".format(len(values)), code="DEPENDENCIES_AVAILABLE"))
    return results
