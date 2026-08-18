from __future__ import absolute_import

import datetime
import math
import os
import platform
import uuid


def _call(api, name, *args):
    method = getattr(api, name, None)
    if not callable(method):
        raise RuntimeError("RenderHive Maya API is missing required helper: {}".format(name))
    return method(*args)


def _split_values(value):
    if not value:
        return []
    result = []
    for item in str(value).replace(";", ",").split(","):
        clean = item.strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _widget_list(widgets, name, default=None):
    widgets = widgets or {}
    widget = widgets.get(name)
    if widget is None:
        return list(default or [])

    if hasattr(widget, "selected_values"):
        try:
            return list(widget.selected_values() or [])
        except Exception:
            pass

    if hasattr(widget, "text"):
        try:
            return _split_values(widget.text())
        except Exception:
            pass

    return list(default or [])


def _validation_summary(report):
    report = report or {}
    summary = report.get("summary", {}) or {}
    return {
        "valid": int(summary.get("ERROR", 0)) == 0,
        "errors": int(summary.get("ERROR", 0)),
        "warnings": int(summary.get("WARNING", 0)),
        "info": int(summary.get("INFO", 0)),
        "passed": int(summary.get("PASSED", 0)),
        "total": int(summary.get("total", 0)),
    }


def build_base_task(api):
    """Build the canonical Maya scene/render values shared by every submit path."""
    scene_name = _call(api, "get_scene_name")
    scene_path = _call(api, "get_scene_path")
    project_path = _call(api, "get_project_path")
    output_path = _call(api, "get_default_output_path")
    frame_start, frame_end = _call(api, "get_frame_range")
    width, height = _call(api, "get_resolution")

    get_text = getattr(api, "get_text")
    get_int = getattr(api, "get_int")
    get_option = getattr(api, "get_option")

    return {
        "job_name": get_text("rh_job_name", scene_name),
        "project_name": get_text(
            "rh_project_name",
            (
                os.path.basename(
                    os.path.normpath(project_path)
                )
                if project_path
                else "RenderHive Project"
            ),
        ),
        "software": "maya",
        "scene_path": get_text("rh_scene_path", scene_path),
        "project_path": get_text("rh_project_path", project_path),
        "output_path": get_text("rh_output_path", output_path),
        "frame_start": get_int("rh_frame_start", frame_start),
        "frame_end": get_int("rh_frame_end", frame_end),
        # RenderHive Maya is intentionally Arnold-only. Keep renderer
        # selection out of task state so legacy scene values cannot route a
        # farm task to an unqualified renderer.
        "renderer": "arnold",
        "camera": get_option("rh_camera", _call(api, "get_renderable_camera")),
        "image_name": get_text("rh_image_name", scene_name),
        "image_format": (
            "jpeg"
            if str(get_option("rh_image_format", "png") or "").lower() == "jpg"
            else str(get_option("rh_image_format", "png") or "png").lower()
        ),
        "frame_padding": get_int("rh_frame_padding", 4),
        "width": get_int("rh_width", width),
        "height": get_int("rh_height", height),
        "priority": get_int("rh_priority", 50),
    }


def _targeting_snapshot(window):
    if window is None:
        return {
            "strategy": "all",
            "selected_ids": [],
            "excluded_ids": [],
            "selected_names": [],
            "excluded_names": [],
            "effective_ids": [],
            "effective_names": [],
            "pool_workers": [],
            "eligible_workers": [],
            "synced": False,
            "stale": True,
            "online_count": 0,
        }

    strategy = window.pool_assignment_strategy_key()
    selected_ids = list(window.selected_pool_ids() or [])
    excluded_ids = list(window.excluded_pool_ids() or [])
    selected_names = list(window.pool_names_from_ids(selected_ids) or [])
    excluded_names = list(window.pool_names_from_ids(excluded_ids) or [])
    effective = list(window.effective_pool_records() or [])

    # Keep the builder independent of Qt/widget classes. The targeting
    # controller owns pool record normalization and exposes stable helpers.
    effective_ids = []
    effective_names = []
    for pool in effective:
        pool_id = ""
        pool_name = ""
        if isinstance(pool, dict):
            pool_id = str(pool.get("id") or "").strip()
            pool_name = str(pool.get("name") or "").strip()
        else:
            pool_id = str(getattr(pool, "id", "") or "").strip()
            pool_name = str(getattr(pool, "name", "") or "").strip()
        if pool_id:
            effective_ids.append(pool_id)
        if pool_name:
            effective_names.append(pool_name)

    return {
        "strategy": strategy,
        "selected_ids": selected_ids,
        "excluded_ids": excluded_ids,
        "selected_names": selected_names,
        "excluded_names": excluded_names,
        "effective_ids": effective_ids,
        "effective_names": effective_names,
        "pool_workers": list(window.effective_pool_worker_ids() or []),
        "eligible_workers": list(window.eligible_worker_ids() or []),
        "synced": bool(window.worker_target_has_sync),
        "stale": bool(window.worker_data_is_stale()),
        "online_count": len(window.online_pool_workers()),
    }


def _render_layer_specs(api, widgets):
    widgets = widgets or {}
    selector_present = "rh_render_layers" in widgets
    selected_names = []
    seen = set()
    for value in _widget_list(widgets, "rh_render_layers", []):
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            selected_names.append(clean)

    selector = widgets.get("rh_render_layers")
    if selector is not None and hasattr(selector, "selected_records"):
        try:
            layer_records = list(selector.selected_records() or [])
        except Exception:
            layer_records = []
        records_for_availability = getattr(selector, "_records", []) or []
    else:
        try:
            records_for_availability = list(_call(api, "get_render_layers") or [])
        except Exception:
            records_for_availability = []
        selected_set = set(selected_names)
        layer_records = [
            item
            for item in records_for_availability
            if isinstance(item, dict)
            and str(item.get("name") or "").strip() in selected_set
        ]

    available_names = {
        str(item.get("name") or "").strip()
        for item in records_for_availability
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }

    # Non-Qt/legacy callers have no explicit selector. Use Maya's renderable
    # scene state as the default so there is still one canonical task builder.
    if not selector_present and not selected_names:
        for item in records_for_availability:
            if not isinstance(item, dict) or not item.get("renderable"):
                continue
            name = str(item.get("name") or "").strip()
            if name and name not in seen:
                seen.add(name)
                selected_names.append(name)
        if not selected_names:
            for item in records_for_availability:
                if not isinstance(item, dict):
                    continue
                if not (item.get("is_current") or item.get("is_default")):
                    continue
                name = str(item.get("name") or "").strip()
                if name:
                    selected_names.append(name)
                    break
        if not selected_names and records_for_availability:
            first = records_for_availability[0]
            if isinstance(first, dict):
                name = str(first.get("name") or "").strip()
                if name:
                    selected_names.append(name)
        selected_set = set(selected_names)
        layer_records = [
            item
            for item in records_for_availability
            if isinstance(item, dict)
            and str(item.get("name") or "").strip() in selected_set
        ]

    layer_by_name = {
        str(item.get("name") or "").strip(): item
        for item in layer_records
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }
    missing = [name for name in selected_names if name not in available_names]
    specs = []
    for name in selected_names:
        record = layer_by_name.get(name)
        if not isinstance(record, dict):
            continue
        specs.append({
            "name": name,
            "display_name": str(record.get("display_name") or name),
            "source": str(record.get("source") or "maya"),
            "renderable": bool(record.get("renderable", True)),
            "is_default": bool(record.get("is_default", name == "defaultRenderLayer")),
        })
    return specs, missing


def _maya_version(api):
    cmds = getattr(api, "cmds", None)
    if cmds is not None:
        try:
            return str(cmds.about(version=True))
        except Exception:
            pass
    return ""


def build_task(api, window=None, widgets=None, validation_report=None):
    """Build the single production task model used by validation and submit."""
    task = dict(build_base_task(api))

    frame_start = int(task.get("frame_start", 1))
    frame_end = int(task.get("frame_end", frame_start))
    frame_step = max(1, int(getattr(api, "get_int")("rh_frame_step", 1)))
    chunk_size = max(1, int(getattr(api, "get_int")("rh_chunk_size", 10)))
    frame_count = (((frame_end - frame_start) // frame_step) + 1) if frame_end >= frame_start else 0
    task_count = int(math.ceil(float(frame_count) / float(chunk_size))) if frame_count else 0

    targeting = _targeting_snapshot(window)
    strategy = targeting["strategy"]
    selected_ids = targeting["selected_ids"]
    excluded_ids = targeting["excluded_ids"]
    selected_names = targeting["selected_names"]
    excluded_names = targeting["excluded_names"]
    effective_ids = targeting["effective_ids"]
    effective_names = targeting["effective_names"]
    pool_workers = targeting["pool_workers"]
    eligible_workers = targeting["eligible_workers"]
    synced = targeting["synced"]
    stale = targeting["stale"]
    online_count = targeting["online_count"]

    display_pool = "All Pools" if strategy == "all" else (
        ", ".join(selected_names if strategy == "selected" else effective_names)
        or "No Pools"
    )
    dependencies = _split_values(getattr(api, "get_text")("rh_job_dependencies", ""))
    task_id = "RH-{}-{}".format(
        datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
        uuid.uuid4().hex[:6].upper(),
    )
    render_layers, missing_layer_names = _render_layer_specs(api, widgets)

    task.update({
        "schema_version": "2.1",
        "task_uid": task_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "render_layers": render_layers,
        "render_layer_names": [item.get("name") for item in render_layers],
        "render_layer_missing_names": missing_layer_names,
        "frame_step": frame_step,
        "chunk_size": chunk_size,
        "concurrent_tasks": getattr(api, "get_int")("rh_concurrent_tasks", 1),
        "pool": display_pool,
        "pool_id": effective_ids[0] if len(effective_ids) == 1 else "",
        "pool_strategy": strategy,
        "selected_pool_ids": selected_ids,
        "selected_pool_names": selected_names,
        "excluded_pool_ids": excluded_ids,
        "excluded_pool_names": excluded_names,
        "effective_pool_ids": effective_ids,
        "effective_pool_names": effective_names,
        "pool_workers": pool_workers,
        "allowed_workers": [],
        "denied_workers": [],
        "eligible_workers": eligible_workers,
        "eligible_worker_count": len(eligible_workers),
        "online_pool_worker_count": online_count,
        "worker_targeting_synced": synced,
        "worker_targeting_stale": stale,
        "worker_assignment_mode": "pool_based",
        "retry_count": getattr(api, "get_int")("rh_retry_count", 2),
        "task_timeout_minutes": getattr(api, "get_int")("rh_timeout_minutes", 0),
        "submission_mode": "Shared Storage",
        "department": getattr(api, "get_text")("rh_department", ""),
        "comment": getattr(api, "get_text")("rh_comment", ""),
        "job_dependencies": dependencies,
        "minimum_cores": getattr(api, "get_int")("rh_minimum_cores", 0),
        "minimum_ram_gb": getattr(api, "get_int")("rh_minimum_ram_gb", 0),
        "minimum_gpus": getattr(api, "get_int")("rh_minimum_gpus", 0),
    })

    task["job"] = {
        "uid": task_id,
        "name": task.get("job_name", ""),
        "project": task.get("project_name", ""),
        "department": task.get("department", ""),
        "comment": task.get("comment", ""),
        "priority": int(task.get("priority", 50)),
        "dependencies": dependencies,
    }
    task["frames"] = {
        "start": frame_start,
        "end": frame_end,
        "step": frame_step,
        "count": frame_count,
        "chunk_size": chunk_size,
        "task_count": task_count,
    }
    task["farm"] = {
        "pool": display_pool,
        "pool_id": task.get("pool_id", ""),
        "pool_strategy": strategy,
        "selected_pool_ids": selected_ids,
        "selected_pool_names": selected_names,
        "excluded_pool_ids": excluded_ids,
        "excluded_pool_names": excluded_names,
        "effective_pool_ids": effective_ids,
        "effective_pool_names": effective_names,
        "pool_workers": pool_workers,
        "concurrent_tasks": task.get("concurrent_tasks", 1),
        "allowed_workers": [],
        "denied_workers": [],
        "worker_selection": {
            "strategy": strategy,
            "selected_pool_ids": selected_ids,
            "selected_pool_names": selected_names,
            "excluded_pool_ids": excluded_ids,
            "excluded_pool_names": excluded_names,
            "effective_pool_ids": effective_ids,
            "effective_pool_names": effective_names,
            "pool_workers": pool_workers,
            "eligible_workers": eligible_workers,
            "eligible_worker_count": len(eligible_workers),
            "online_pool_worker_count": online_count,
            "synced": synced,
            "stale": stale,
        },
        "hardware": {
            "minimum_cores": task.get("minimum_cores", 0),
            "minimum_ram_gb": task.get("minimum_ram_gb", 0),
            "minimum_gpus": task.get("minimum_gpus", 0),
        },
    }
    task["failure_policy"] = {
        "retry_count": task.get("retry_count", 2),
        "task_timeout_minutes": task.get("task_timeout_minutes", 0),
    }
    task["submission"] = {
        "mode": task.get("submission_mode", "Shared Storage"),
        "scene_path": task.get("scene_path", ""),
        "project_path": task.get("project_path", ""),
        "output_path": task.get("output_path", ""),
    }
    task["software_info"] = {
        "dcc": "maya",
        "maya_version": _maya_version(api),
        "renderer": task.get("renderer", ""),
        "host_os": platform.system(),
    }
    if validation_report is None:
        validation_report = getattr(api, "VALIDATION_REPORT", {}) or {}
    task["validation"] = _validation_summary(validation_report)
    return task
