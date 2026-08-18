from __future__ import absolute_import

import os
import uuid


ARNOLD_IMAGE_FORMATS = {"exr", "png", "jpg", "jpeg", "tif", "tiff"}
POOL_STRATEGIES = {"all", "selected", "all_except"}


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _clean_text(value):
    return str(value or "").strip()


def _unique_nonempty(values):
    result = []
    for value in values or []:
        text = _clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def validate_task(task):
    """Return blocking production submission errors for a Maya task.

    Scene-level validation stays in ``validation/``.  This function is the
    final, side-effect-free guard shared by the classic Maya API and the Qt
    submitter immediately before the payload is sent to the backend.
    """
    task = task or {}
    errors = []

    if not _clean_text(task.get("job_name")):
        errors.append("Job name is empty.")

    scene_path = _clean_text(task.get("scene_path"))
    if not scene_path:
        errors.append("Scene path is empty. Save the Maya scene first.")
    elif not os.path.isfile(scene_path):
        errors.append("Scene file does not exist:\n{}".format(scene_path))

    project_path = _clean_text(task.get("project_path"))
    if not project_path:
        errors.append("Project path is empty.")
    elif not os.path.isdir(project_path):
        errors.append("Project path does not exist:\n{}".format(project_path))

    output_path = _clean_text(task.get("output_path"))
    if not output_path:
        errors.append("Output path is empty.")
    elif os.path.exists(output_path) and not os.path.isdir(output_path):
        errors.append("Output path is not a directory:\n{}".format(output_path))

    frame_start = _integer(task.get("frame_start"), 1)
    frame_end = _integer(task.get("frame_end"), frame_start)
    if frame_start > frame_end:
        errors.append("Frame start cannot be greater than frame end.")

    if _integer(task.get("frame_step"), 1) < 1:
        errors.append("Frame step must be at least 1.")
    if _integer(task.get("chunk_size"), 1) < 1:
        errors.append("Chunk size must be at least 1.")
    if _integer(task.get("concurrent_tasks"), 1) < 1:
        errors.append("Tasks per Worker must be at least 1.")
    if _integer(task.get("retry_count"), 0) < 0:
        errors.append("Retry attempts cannot be negative.")
    if _integer(task.get("task_timeout_minutes"), 0) < 0:
        errors.append("Task timeout cannot be negative.")

    if _clean_text(task.get("camera")) in ("", "NoCamera"):
        errors.append("No valid camera selected.")

    if _clean_text(task.get("renderer")).lower() != "arnold":
        errors.append("RenderHive Maya currently supports Arnold only.")

    image_name = _clean_text(task.get("image_name"))
    if not image_name:
        errors.append("Image name is empty.")

    image_format = _clean_text(task.get("image_format")).lower().lstrip(".")
    if image_format == "jpg":
        image_format = "jpeg"
    if not image_format:
        errors.append("Image format is empty.")
    elif image_format not in ARNOLD_IMAGE_FORMATS:
        errors.append("Unsupported Arnold image format: {}.".format(image_format))

    if _integer(task.get("frame_padding"), 0) < 1:
        errors.append("Frame padding must be at least 1.")

    if _integer(task.get("width"), 0) <= 0 or _integer(task.get("height"), 0) <= 0:
        errors.append("Resolution must be greater than zero.")

    for key, label in (
        ("minimum_cores", "Minimum CPU cores"),
        ("minimum_ram_gb", "Minimum RAM"),
        ("minimum_gpus", "Minimum GPU count"),
    ):
        if _integer(task.get(key), 0) < 0:
            errors.append("{} cannot be negative.".format(label))

    missing_layers = _unique_nonempty(task.get("render_layer_missing_names"))
    if missing_layers:
        errors.append(
            "Selected render layer(s) no longer exist in Maya: {}. "
            "Refresh the layer list and select again.".format(", ".join(missing_layers))
        )

    render_layers = task.get("render_layers") or []
    if not render_layers:
        errors.append("Select at least one Maya render layer.")
    else:
        names = []
        for layer in render_layers:
            name = _clean_text(layer.get("name")) if isinstance(layer, dict) else _clean_text(layer)
            if not name:
                errors.append("A selected render layer has no valid Maya layer name.")
                continue
            if name in names:
                errors.append("Render layer is selected more than once: {}".format(name))
            else:
                names.append(name)

    strategy = _clean_text(task.get("pool_strategy") or "all").lower()
    if strategy not in POOL_STRATEGIES:
        errors.append("Unknown pool assignment strategy: {}.".format(strategy or "<empty>"))
    selected = set(_unique_nonempty(task.get("selected_pool_ids")))
    excluded = set(_unique_nonempty(task.get("excluded_pool_ids")))
    effective = set(_unique_nonempty(task.get("effective_pool_ids")))
    for pool_id in sorted(selected.union(excluded).union(effective)):
        try:
            uuid.UUID(pool_id)
        except (ValueError, AttributeError, TypeError):
            errors.append("Pool id is not a valid RenderHive UUID: {}".format(pool_id))
    overlap = sorted(selected.intersection(excluded))
    if overlap:
        errors.append("Pools cannot be both selected and excluded: {}".format(", ".join(overlap)))
    if strategy == "selected" and not selected:
        errors.append("Select at least one pool when using Selected Pools Only.")
    if strategy == "all_except" and not effective:
        errors.append("At least one pool must remain after applying exclusions.")

    seen_dependencies = set()
    for dependency in task.get("job_dependencies") or []:
        text = _clean_text(dependency)
        try:
            normalized = str(uuid.UUID(text))
        except (ValueError, AttributeError, TypeError):
            errors.append("Job dependency must be a valid RenderHive Job UUID: {}".format(dependency))
            continue
        if normalized in seen_dependencies:
            errors.append("Job dependency is selected more than once: {}".format(normalized))
        seen_dependencies.add(normalized)

    validation = task.get("validation") or {}
    if _integer(validation.get("errors"), 0) > 0:
        errors.append("Scene validation still contains blocking errors.")

    return errors
