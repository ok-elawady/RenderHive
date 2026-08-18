from __future__ import absolute_import

import uuid


CATEGORY = "Submission"
VALID_POOL_STRATEGIES = {"all", "selected", "all_except"}


def make_result(severity, code, message, fixable=False, data=None):
    return {
        "severity": severity,
        "category": CATEGORY,
        "code": code,
        "node": "",
        "message": message,
        "fixable": bool(fixable),
        "data": data or {},
    }


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _values(value):
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item or "").strip() for item in value if str(item or "").strip()]


def check_scheduling(context):
    results = []
    checks = (
        ("frame_step", 1, "FRAME_STEP_INVALID", "Frame step must be at least 1."),
        ("chunk_size", 1, "CHUNK_SIZE_INVALID", "Chunk size must be at least 1."),
        ("concurrent_tasks", 1, "TASKS_PER_WORKER_INVALID", "Tasks per Worker must be at least 1."),
        ("retry_count", 0, "RETRY_COUNT_INVALID", "Retry attempts cannot be negative."),
        ("task_timeout_minutes", 0, "TASK_TIMEOUT_INVALID", "Task timeout cannot be negative."),
    )
    for key, minimum, code, message in checks:
        value = _integer(context.get(key), minimum)
        if value < minimum:
            results.append(make_result("ERROR", code, message, data={key: value}))

    if not results:
        results.append(make_result(
            "PASSED",
            "SCHEDULING_VALID",
            "Scheduling, retry and timeout values are valid.",
        ))
    return results


def check_hardware_requirements(context):
    results = []
    requirements = {
        "minimum_cores": _integer(context.get("minimum_cores"), 0),
        "minimum_ram_gb": _integer(context.get("minimum_ram_gb"), 0),
        "minimum_gpus": _integer(context.get("minimum_gpus"), 0),
    }
    invalid = [key for key, value in requirements.items() if value < 0]
    if invalid:
        results.append(make_result(
            "ERROR",
            "HARDWARE_REQUIREMENTS_INVALID",
            "Worker hardware requirements cannot be negative.",
            data=requirements,
        ))
        return results

    synced = bool(context.get("worker_targeting_synced"))
    eligible_count = _integer(context.get("eligible_worker_count"), 0)
    online_count = _integer(context.get("online_pool_worker_count"), 0)
    has_requirements = any(requirements.values())

    if synced and online_count > 0 and eligible_count == 0 and has_requirements:
        results.append(make_result(
            "WARNING",
            "NO_WORKER_MEETS_HARDWARE_REQUIREMENTS",
            "Online workers exist in the targeted pools, but none match the CPU/RAM/GPU requirements.",
            data=requirements,
        ))
    else:
        results.append(make_result(
            "PASSED",
            "HARDWARE_REQUIREMENTS_VALID",
            "Worker hardware requirements are valid.",
            data=requirements,
        ))
    return results


def check_pool_targeting(context):
    strategy = str(context.get("pool_strategy") or "all").strip().lower()
    selected = set(_values(context.get("selected_pool_ids")))
    excluded = set(_values(context.get("excluded_pool_ids")))
    effective = set(_values(context.get("effective_pool_ids")))
    results = []

    for pool_id in sorted(selected.union(excluded).union(effective)):
        try:
            uuid.UUID(pool_id)
        except (ValueError, AttributeError, TypeError):
            results.append(make_result(
                "ERROR",
                "POOL_ID_INVALID",
                "Pool id is not a valid RenderHive UUID: {}.".format(pool_id),
                data={"pool_id": pool_id},
            ))

    if strategy not in VALID_POOL_STRATEGIES:
        return [make_result(
            "ERROR",
            "POOL_STRATEGY_INVALID",
            "Unknown pool assignment strategy: {}.".format(strategy or "<empty>"),
        )]

    overlap = sorted(selected.intersection(excluded))
    if overlap:
        results.append(make_result(
            "ERROR",
            "POOL_SELECTION_CONFLICT",
            "Pools cannot be both selected and excluded: {}.".format(", ".join(overlap)),
            data={"pool_ids": overlap},
        ))
    if strategy == "selected" and not selected:
        results.append(make_result(
            "ERROR",
            "POOL_SELECTION_EMPTY",
            "Selected Pools Only requires at least one pool.",
        ))
    if strategy == "all_except" and not effective:
        results.append(make_result(
            "ERROR",
            "POOL_EXCLUSION_REMOVES_ALL",
            "All Except Selected must leave at least one pool available.",
        ))

    if not bool(context.get("worker_targeting_synced")):
        results.append(make_result(
            "WARNING",
            "WORKER_TARGETING_NOT_SYNCED",
            "Worker and pool targeting has not been synchronized with the backend yet.",
        ))

    if not results:
        results.append(make_result(
            "PASSED",
            "POOL_TARGETING_VALID",
            "Pool targeting is valid.",
        ))
    return results


def check_job_dependencies(context):
    results = []
    seen = set()
    dependencies = _values(context.get("job_dependencies"))
    for dependency in dependencies:
        try:
            normalized = str(uuid.UUID(dependency))
        except (ValueError, AttributeError, TypeError):
            results.append(make_result(
                "ERROR",
                "JOB_DEPENDENCY_INVALID",
                "Job dependency is not a valid RenderHive UUID: {}.".format(dependency),
                data={"job_id": dependency},
            ))
            continue
        if normalized in seen:
            results.append(make_result(
                "ERROR",
                "JOB_DEPENDENCY_DUPLICATE",
                "Job dependency is selected more than once: {}.".format(normalized),
                data={"job_id": normalized},
            ))
        seen.add(normalized)

    if not results:
        results.append(make_result(
            "PASSED",
            "JOB_DEPENDENCIES_VALID",
            "Job dependencies are valid." if dependencies else "No job dependencies are required.",
            data={"count": len(dependencies)},
        ))
    return results


def run_checks(context):
    results = []
    for check in (
        check_scheduling,
        check_hardware_requirements,
        check_pool_targeting,
        check_job_dependencies,
    ):
        results.extend(check(context) or [])
    return results
