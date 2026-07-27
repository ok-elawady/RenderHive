"""
Business logic for the jobs app.

This module contains pure Python service functions with no dependency on Django
views or request objects. Serializers and views call these functions to keep
themselves thin.
"""

import re
import time

from django.db import transaction
from django.db.models import F


def generate_job_name(project: str, user: str, visible_name: str) -> str:
    """Generate a stable, system-unique job identifier.

    The name is auto-generated and never authored by the artist. It is used by
    CLI tools and the API for exact targeting. Mirrors OpenCue's ``str_name``
    convention of ``{show}-{user}-{shot}-{epoch_ms}``.

    Args:
        project: The active show or production segment (e.g. ``proj_x_ep03``).
        user: The submitter's display name.
        visible_name: The human-readable label typed by the artist.

    Returns:
        A unique, filesystem-safe job name string.
    """
    import uuid

    epoch_ms = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:4]

    # Sanitize each part: lowercase, replace non-alphanumeric with underscore
    def sanitize(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

    return f"{sanitize(project)}-{sanitize(user)}-{sanitize(visible_name)}-{epoch_ms}-{uid}"


def expand_frame_range(frame_range: str, chunk_size: int = 1) -> list[tuple[int, int]]:
    """Parse a VFX frame range descriptor into a list of frame chunks.

    Supports the following range formats:
    - Simple: ``1-100``
    - Step: ``1-100x2`` (every 2nd frame: 1, 3, 5, ...)
    - List: ``1,5,10``
    - Mixed: ``1-50,75,100-200x5``

    For chunked layers (``chunk_size > 1``), the range is split into chunks of
    the specified size, returning the start and end frame for each chunk.

    Args:
        frame_range: A VFX frame range descriptor string.
        chunk_size: Number of consecutive frames per task.

    Returns:
        A list of tuples (chunk_start, chunk_end).

    Raises:
        ValueError: If the frame range string contains an invalid segment.
    """
    frames = []
    segments = frame_range.split(",")

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        step_match = re.match(r"^(-?\d+)-(-?\d+)x(\d+)$", segment)
        range_match = re.match(r"^(-?\d+)-(-?\d+)$", segment)
        single_match = re.match(r"^-?\d+$", segment)

        if step_match:
            start, end, step = int(step_match.group(1)), int(step_match.group(2)), int(step_match.group(3))
            if step <= 0:
                raise ValueError(f"Step must be positive in segment: '{segment}'")
            frames.extend(range(start, end + 1, step))
        elif range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            frames.extend(range(start, end + 1))
        elif single_match:
            frames.append(int(segment))
        else:
            raise ValueError(f"Invalid frame range segment: '{segment}'")

    # Deduplicate and sort
    frames = sorted(set(frames))

    # Apply chunking: return the start and end frame of each chunk
    chunks = []
    if chunk_size > 1:
        for i in range(0, len(frames), chunk_size):
            chunk = frames[i:i + chunk_size]
            chunks.append((chunk[0], chunk[-1]))
    else:
        for f in frames:
            chunks.append((f, f))

    return chunks


@transaction.atomic
def create_job_with_layers(validated_data: dict, submitted_by=None):
    """Create a Job with its Layers and Tasks in a single atomic transaction.

    This is the canonical job submission path. It is called by
    ``JobCreateSerializer.create()`` and must not be called directly from views.

    The function:
    1. Pops the nested ``layers`` data from ``validated_data``.
    2. Creates the ``Job`` row.
    3. For each layer, creates the ``Layer`` row and bulk-creates all ``Task``
       rows derived from expanding the ``frame_range``.

    Args:
        validated_data: The deserialized, validated data dict from the serializer.
            Must contain a ``layers`` key with a list of layer data dicts.
        submitted_by: The authenticated ``User`` instance (web submissions only).
            ``None`` for DCC plugin submissions.

    Returns:
        The newly created ``Job`` instance with all related rows committed.

    Raises:
        ValueError: If any layer's ``frame_range`` is invalid.
    """
    from apps.jobs.models import Task, TaskState, Job, Layer

    layers_data = validated_data.pop("layers")
    included_pools = validated_data.pop("included_pools", [])
    excluded_pools = validated_data.pop("excluded_pools", [])

    # Guard against overlapping pools. At the API layer this is caught by the
    # serializer's validate() method, but this service may also be called
    # programmatically (e.g. management commands, tests), so we validate here too.
    included_pks = {getattr(p, "pk", p) for p in included_pools}
    excluded_pks = {getattr(p, "pk", p) for p in excluded_pools}
    if included_pks & excluded_pks:
        raise ValueError("A pool cannot be both included and excluded.")

    # The Job model's save() method will auto-generate the name if not provided.

    job = Job.objects.create(submitted_by=submitted_by, **validated_data)

    if included_pools:
        job.included_pools.set(included_pools)
    if excluded_pools:
        job.excluded_pools.set(excluded_pools)

    for layer_data in layers_data:
        frame_range = layer_data["frame_range"]
        chunk_size = layer_data.get("chunk_size", 1)
        max_retries = layer_data.get("max_retries", 3)

        frame_starts = expand_frame_range(frame_range, chunk_size)

        layer = Layer.objects.create(job=job, **layer_data)

        # Bulk-create Task rows for efficiency
        tasks = []
        for i, (start_number, end_number) in enumerate(frame_starts):
            padded = str(start_number).zfill(4)
            # Since dependencies are not passed in create_job, depend_count is 0
            # Initialize to READY immediately so workers can dispatch them
            initial_state = TaskState.READY

            tasks.append(
                Task(
                    layer=layer,
                    job=job,
                    name=f"{layer.name}_{padded}",
                    frame_start=start_number,
                    frame_end=end_number,
                    dispatch_order=i,
                    state=initial_state,
                    depend_count=0,
                    max_retries=max_retries,
                )
            )

        Task.objects.bulk_create(tasks)

        # Update layer and job counters after bulk_create
        # (signals do not fire on bulk_create, so we set them directly)
        task_count = len(tasks)
        Layer.objects.filter(pk=layer.pk).update(
            total_tasks=task_count,
            ready_tasks=task_count,
        )
        Job.objects.filter(pk=job.pk).update(
            total_tasks=F("total_tasks") + task_count,
            ready_tasks=F("ready_tasks") + task_count,
        )

    job.refresh_from_db()
    return job
