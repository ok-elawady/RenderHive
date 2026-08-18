"""Backend pool, hardware and Houdini capability checks."""

from __future__ import absolute_import

import uuid

from renderhive_houdini.api.models import worker_meets_requirements, worker_supports_houdini
from renderhive_houdini.validation.result import ValidationResult


def _worker_pool_ids(worker, pools):
    worker_id = str((worker or {}).get("id") or "")
    result = set()
    for item in (worker or {}).get("pools") or []:
        if isinstance(item, dict) and item.get("id"):
            result.add(str(item.get("id")))
    for pool in pools or []:
        pool_id = str(pool.get("id") or "")
        for member in pool.get("workers") or []:
            member_id = str(member.get("id") or member.get("worker_id") or "") if isinstance(member, dict) else str(member or "")
            if worker_id and member_id == worker_id and pool_id:
                result.add(pool_id)
    return result


def _valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def run(context, node_info, farm_context=None):
    data = dict(farm_context or {})
    if not data:
        return [ValidationResult("INFO", "Farm", "Farm compatibility has not been checked yet.", code="FARM_NOT_CHECKED")]
    if not data.get("backend_online"):
        return [ValidationResult("ERROR", "Farm", "RenderHive backend is offline.", code="BACKEND_OFFLINE")]

    results = []
    workers = list(data.get("workers") or [])
    pools = list(data.get("pools") or [])
    strategy = str(data.get("pool_strategy") or "all").lower()
    selected_ids = [str(item) for item in data.get("selected_pool_ids") or [] if str(item)]
    effective_ids = set(str(item) for item in data.get("effective_pool_ids") or [] if str(item))

    if strategy == "selected_only" and not selected_ids:
        results.append(ValidationResult("ERROR", "Farm", "Selected Pools Only requires at least one pool.", code="POOL_SELECTION_REQUIRED"))
    invalid_pool_ids = [value for value in selected_ids if not _valid_uuid(value)]
    if invalid_pool_ids:
        results.append(ValidationResult("ERROR", "Farm", "Pool targeting contains invalid backend UUIDs.", code="POOL_UUID_INVALID", data={"values": invalid_pool_ids}))

    min_cores = int(data.get("min_cores") or 0)
    min_memory_mb = int(data.get("min_memory_mb") or 0)
    min_gpus = int(data.get("min_gpus") or 0)
    nodes = list(data.get("render_nodes") or [])
    if not nodes and node_info is not None:
        nodes = [node_info]

    version = getattr(context, "houdini_version", "") if context else ""
    any_source_without_worker = False
    eligible_union = set()
    for node in nodes or [None]:
        eligible = []
        renderer = getattr(node, "renderer", "") if node is not None else ""
        source_min_gpus = max(min_gpus, 1 if "xpu" in str(renderer or "").lower() else 0)
        for worker in workers:
            pool_ids = _worker_pool_ids(worker, pools)
            if effective_ids and not pool_ids.intersection(effective_ids):
                continue
            if not worker_meets_requirements(worker, min_cores, min_memory_mb, source_min_gpus):
                continue
            if not worker_supports_houdini(
                worker,
                version,
                getattr(node, "execution_mode", "") if node is not None else "",
                renderer,
            ):
                continue
            eligible.append(worker)
            eligible_union.add(str(worker.get("id") or ""))
        if node is not None and not eligible:
            any_source_without_worker = True
            results.append(ValidationResult(
                "ERROR",
                "Farm",
                "No compatible online worker is eligible for render source {} ({} / {}).".format(
                    getattr(node, "path", "Unknown"),
                    getattr(node, "renderer", "Unknown"),
                    getattr(node, "execution_mode", "Unknown"),
                ),
                getattr(node, "path", ""),
                code="FARM_SOURCE_NO_ELIGIBLE_WORKER",
            ))

    if not any_source_without_worker:
        results.append(ValidationResult(
            "PASSED", "Farm",
            "{} compatible online worker(s) can execute the selected Houdini source(s).".format(len([value for value in eligible_union if value])),
            code="FARM_WORKERS_ELIGIBLE",
            data={"eligible_worker_ids": sorted(value for value in eligible_union if value)},
        ))

    dependencies = [str(value or "").strip() for value in data.get("job_dependencies") or [] if str(value or "").strip()]
    invalid_dependencies = [value for value in dependencies if not _valid_uuid(value)]
    if invalid_dependencies:
        results.append(ValidationResult("ERROR", "Dependencies", "Job dependencies contain invalid backend UUIDs.", code="JOB_DEPENDENCY_UUID_INVALID", data={"values": invalid_dependencies}))
    elif dependencies:
        results.append(ValidationResult("PASSED", "Dependencies", "{} backend job dependency/dependencies selected.".format(len(set(dependencies))), code="JOB_DEPENDENCIES_VALID"))
    else:
        results.append(ValidationResult("INFO", "Dependencies", "No backend job dependencies selected.", code="JOB_DEPENDENCIES_NONE"))

    return results
