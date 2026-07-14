"""
Business logic for the jobs app.

This module contains pure Python service functions with no dependency on Django
views or request objects. Serializers and views call these functions to keep
themselves thin.
"""

import re
import time

from django.db import transaction


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
    epoch_ms = int(time.time() * 1000)

    # Sanitize each part: lowercase, replace non-alphanumeric with underscore
    def sanitize(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

    return f"{sanitize(project)}-{sanitize(user)}-{sanitize(visible_name)}-{epoch_ms}"


def expand_frame_range(frame_range: str, chunk_size: int = 1) -> list[int]:
    """Parse a VFX frame range descriptor into a list of frame start numbers.

    Supports the following range formats:
    - Simple: ``1-100``
    - Step: ``1-100x2`` (every 2nd frame: 1, 3, 5, ...)
    - List: ``1,5,10``
    - Mixed: ``1-50,75,100-200x5``

    For chunked layers (``chunk_size > 1``), only the first frame of each
    chunk is returned. For example, ``1-10`` with ``chunk_size=5`` returns
    ``[1, 6]``.

    Args:
        frame_range: A VFX frame range descriptor string.
        chunk_size: Number of consecutive frames per Frame record.

    Returns:
        A sorted list of unique frame numbers (start of each chunk).

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

    # Apply chunking: return only the start frame of each chunk
    if chunk_size > 1:
        frames = [frames[i] for i in range(0, len(frames), chunk_size)]

    return frames


@transaction.atomic
def create_job_with_layers(validated_data: dict, submitted_by=None):
    """Create a Job with its Layers and Frames in a single atomic transaction.

    This is the canonical job submission path. It is called by
    ``JobCreateSerializer.create()`` and must not be called directly from views.

    The function:
    1. Pops the nested ``layers`` data from ``validated_data``.
    2. Creates the ``Job`` row.
    3. For each layer, creates the ``Layer`` row and bulk-creates all ``Frame``
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
    from apps.jobs.models import Frame, FrameState, Job, Layer

    layers_data = validated_data.pop("layers")

    # Generate a stable system name if not provided
    if not validated_data.get("name"):
        validated_data["name"] = generate_job_name(
            project=validated_data.get("project", "unknown"),
            user=validated_data.get("user", "unknown"),
            visible_name=validated_data.get("visible_name", "job"),
        )

    job = Job.objects.create(submitted_by=submitted_by, **validated_data)

    for layer_data in layers_data:
        frame_range = layer_data["frame_range"]
        chunk_size = layer_data.get("chunk_size", 1)
        max_retries = layer_data.get("max_retries", 3)

        frame_starts = expand_frame_range(frame_range, chunk_size)

        layer = Layer.objects.create(job=job, **layer_data)

        # Bulk-create Frame rows for efficiency
        frames = []
        for i, start_number in enumerate(frame_starts):
            padded = str(start_number).zfill(4)
            frames.append(
                Frame(
                    layer=layer,
                    job=job,
                    name=f"{layer.name}_{padded}",
                    number=start_number,
                    dispatch_order=i,
                    state=FrameState.WAITING,
                    max_retries=max_retries,
                )
            )

        Frame.objects.bulk_create(frames)

        # Update layer and job counters after bulk_create
        # (signals do not fire on bulk_create, so we set them directly)
        frame_count = len(frames)
        Layer.objects.filter(pk=layer.pk).update(
            total_frames=frame_count,
            waiting_frames=frame_count,
        )
        Job.objects.filter(pk=job.pk).update(
            total_frames=Job.objects.filter(pk=job.pk).values_list("total_frames", flat=True)[0] + frame_count,
            waiting_frames=Job.objects.filter(pk=job.pk).values_list("waiting_frames", flat=True)[0] + frame_count,
        )

    job.refresh_from_db()
    return job
