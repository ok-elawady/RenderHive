"""
Business logic for the jobs app.

This module contains pure Python service functions with no dependency on Django
views or request objects. Serializers and views call these functions to keep
themselves thin.
"""

import re
import time
import uuid

from django.db import transaction
from django.db.models import F


def check_dependency_cycle(dep_entity_id: str, parent_entity_id: str, entity_type: str) -> bool:
    """Return True if adding (parent_entity → dep_entity) would form a cycle.

    Performs a breadth-first walk upward from *parent_entity_id*, following
    existing dependency edges of the same *entity_type*, to check whether
    *dep_entity_id* is already an ancestor of *parent_entity_id*.  If it is,
    adding the new edge would close a cycle.

    Args:
        dep_entity_id: The entity that would be *blocked* by this new dep.
        parent_entity_id: The entity that must complete *first*.
        entity_type: One of ``"task"``, ``"layer"``, or ``"job"``.  Controls
            which FK columns are traversed.

    Returns:
        True  → cycle detected (the proposed dependency must be rejected).
        False → safe to add.
    """
    from apps.jobs.models import Dependency, DependencyType

    type_map = {
        "task": (DependencyType.TASK_ON_TASK, "parent_task_id", "dep_task_id"),
        "layer": (DependencyType.LAYER_ON_LAYER, "parent_layer_id", "dep_layer_id"),
        "job": (DependencyType.JOB_ON_JOB, "parent_job_id", "dep_job_id"),
    }
    dep_type, parent_field, dep_field = type_map[entity_type]

    visited = set()
    frontier = {str(parent_entity_id)}

    while frontier:
        # If the blocked entity is already an ancestor of the proposed parent,
        # adding this edge would close a loop.
        if str(dep_entity_id) in frontier:
            return True

        visited |= frontier

        # Collect all entities that the current frontier itself depends ON
        # (i.e. walk upward: what do these entities block ON?)
        ancestor_ids = (
            Dependency.objects.filter(
                **{f"{dep_field}__in": frontier},
                type=dep_type,
                is_satisfied=False,
            )
            .values_list(parent_field, flat=True)
            .distinct()
        )

        frontier = {str(a) for a in ancestor_ids} - visited

    return False


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



def _submission_metadata(layers_data: list[dict]) -> tuple[dict, bool]:
    """Return worker-targeting metadata and start-suspended state.

    Current DCC submitters keep these values in ``Layer.scene_info`` so the
    backend can support pool routing without forcing every plugin release to
    know the latest top-level serializer contract.
    """

    targeting: dict = {}
    start_suspended = False
    for layer_data in layers_data:
        if not isinstance(layer_data, dict):
            continue
        scene_info = layer_data.get("scene_info")
        if not isinstance(scene_info, dict):
            continue
        if not targeting:
            candidate = scene_info.get("worker_targeting")
            if isinstance(candidate, dict):
                targeting = candidate
        start_suspended = start_suspended or bool(scene_info.get("start_suspended"))
    return targeting, start_suspended


def _resolve_targeting_pools(targeting: dict) -> tuple[list, list]:
    """Resolve submitter pool IDs into WorkerPool model instances."""

    from apps.workers.models import WorkerPool

    strategy = str(targeting.get("strategy") or "all").strip().lower()
    if strategy in {"selected", "selected-only", "selected_pools_only"}:
        strategy = "selected_only"
    elif strategy in {"exclude", "all-except-selected", "all_except"}:
        strategy = "all_except_selected"

    if strategy == "selected_only":
        raw_ids = targeting.get("effective_pool_ids") or targeting.get("selected_pool_ids") or []
        destination = "included"
    elif strategy == "all_except_selected":
        raw_ids = targeting.get("excluded_pool_ids") or targeting.get("selected_pool_ids") or []
        destination = "excluded"
    else:
        return [], []

    normalized_ids = []
    for value in raw_ids:
        try:
            normalized_ids.append(uuid.UUID(str(value)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"Invalid worker pool id: {value}") from exc

    if not normalized_ids:
        if strategy == "selected_only":
            raise ValueError("Selected Pools Only requires at least one worker pool.")
        return [], []

    pools_by_id = {
        pool.pk: pool
        for pool in WorkerPool.objects.filter(pk__in=normalized_ids)
    }
    missing = [str(pool_id) for pool_id in normalized_ids if pool_id not in pools_by_id]
    if missing:
        raise ValueError("Unknown worker pool id(s): {}".format(", ".join(missing)))

    pools = [pools_by_id[pool_id] for pool_id in normalized_ids]
    return (pools, []) if destination == "included" else ([], pools)


@transaction.atomic
def create_job_with_layers(validated_data: dict, submitted_by=None):
    """Create a Job with its Layers and Tasks in a single atomic transaction.

    This is the canonical job submission path. It is called by
    ``JobCreateSerializer.create()`` and must not be called directly from views.

    The function:
    1. Pops the nested ``layers`` and optional ``dependencies`` data.
    2. Creates the ``Job`` row.
    3. For each layer, creates the ``Layer`` row and bulk-creates all ``Task``
       rows derived from expanding the ``frame_range``.
    4. If ``dependencies`` is provided, creates ``Dependency`` rows linking
       layers and sets blocked tasks to WAITING with correct counter values.

    Args:
        validated_data: The deserialized, validated data dict from the serializer.
            Must contain a ``layers`` key with a list of layer data dicts.
            May contain an optional ``dependencies`` key with a list of dicts:
            ``[{"dep_layer_name": str, "parent_layer_name": str}]``.
        submitted_by: The authenticated ``User`` instance (web submissions only).
            ``None`` for DCC plugin submissions.

    Returns:
        The newly created ``Job`` instance with all related rows committed.

    Raises:
        ValueError: If any layer's ``frame_range`` is invalid or a layer name
            referenced in ``dependencies`` does not exist on this job.
    """
    from apps.jobs.models import Dependency, DependencyType, Job, JobState, Layer, Task, TaskState

    layers_data = validated_data.pop("layers")
    dependencies_data = validated_data.pop("dependencies", [])
    included_pools = validated_data.pop("included_pools", [])
    excluded_pools = validated_data.pop("excluded_pools", [])

    targeting, start_suspended = _submission_metadata(layers_data)
    if not included_pools and not excluded_pools and targeting:
        included_pools, excluded_pools = _resolve_targeting_pools(targeting)

    if start_suspended:
        validated_data["is_paused"] = True
        validated_data["state"] = JobState.PAUSED

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

    # Track created layers by name for dependency resolution below
    created_layers: dict[str, Layer] = {}

    # Extract execution dependency metadata up-front so layer_data dicts stay
    # clean for Layer.objects.create() — no model fields are added or removed.
    layer_dep_specs = [
        {
            "execution_mode": ld.pop("execution_mode", "IMMEDIATE"),
            "depends_on_layer": ld.pop("depends_on_layer", None),
            "dependency_type": ld.pop("dependency_type", None),
        }
        for ld in layers_data
    ]

    for layer_data in layers_data:
        frame_range = layer_data["frame_range"]
        chunk_size = layer_data.get("chunk_size", 1)
        max_retries = layer_data.get("max_retries", 3)

        frame_starts = expand_frame_range(frame_range, chunk_size)

        layer = Layer.objects.create(job=job, **layer_data)

        created_layers[layer.name] = layer

        # Bulk-create Task rows for efficiency.
        # All tasks start as READY; tasks that are actually blocked by a
        # LAYER_ON_LAYER dep will be corrected to WAITING below.
        tasks = []
        for i, (start_number, end_number) in enumerate(frame_starts):
            padded = str(start_number).zfill(4)
            tasks.append(
                Task(
                    layer=layer,
                    job=job,
                    name=f"{layer.name}_{padded}",
                    frame_start=start_number,
                    frame_end=end_number,
                    dispatch_order=i,
                    state=TaskState.READY,
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

    # ── Process Internal Layer Dependencies ───────────────────────────────────
    for layer_data, dep_spec in zip(layers_data, layer_dep_specs):
        execution_mode = dep_spec["execution_mode"]
        if execution_mode == "IMMEDIATE":
            continue

        dep_layer_name = layer_data["name"]
        dep_layer = created_layers.get(dep_layer_name)

        parent_layers_to_link = []

        if execution_mode == "LAST":
            parent_layers_to_link = [
                layer for name, layer in created_layers.items() if name != dep_layer_name
            ]
            dependency_type = DependencyType.LAYER_ON_LAYER

        elif execution_mode == "WAIT_LAYER":
            parent_name = dep_spec["depends_on_layer"]
            if not parent_name:
                continue
            parent_layer = created_layers.get(parent_name)
            if not parent_layer:
                raise ValueError(f"Layer '{parent_name}' not found on this job.")

            parent_layers_to_link = [parent_layer]
            dependency_type = dep_spec["dependency_type"] or DependencyType.LAYER_ON_LAYER

        for parent_layer in parent_layers_to_link:
            if dep_layer.pk == parent_layer.pk:
                continue
                
            if check_dependency_cycle(dep_layer.pk, parent_layer.pk, "layer"):
                raise ValueError(
                    f"Adding '{dep_layer_name}' → '{parent_layer.name}' dependency would create a cycle."
                )

            if dependency_type == DependencyType.TASK_ON_TASK:
                dep_tasks = list(Task.objects.filter(layer=dep_layer).order_by("frame_start"))
                parent_tasks = list(Task.objects.filter(layer=parent_layer).order_by("frame_start"))
                
                parent_tasks_by_frame = {t.frame_start: t for t in parent_tasks}
                
                deps_to_create = []
                tasks_to_update = []
                for dt in dep_tasks:
                    pt = parent_tasks_by_frame.get(dt.frame_start)
                    if pt:
                        deps_to_create.append(
                            Dependency(
                                type=DependencyType.TASK_ON_TASK,
                                dep_job=job,
                                dep_layer=dep_layer,
                                dep_task=dt,
                                parent_job=job,
                                parent_layer=parent_layer,
                                parent_task=pt,
                            )
                        )
                        dt.state = TaskState.WAITING
                        dt.depend_count += 1
                        tasks_to_update.append(dt)
                        
                if deps_to_create:
                    Dependency.objects.bulk_create(deps_to_create)
                    Task.objects.bulk_update(tasks_to_update, ["state", "depend_count"])
                    
                    blocked_count = len(tasks_to_update)
                    Layer.objects.filter(pk=dep_layer.pk).update(
                        ready_tasks=F("ready_tasks") - blocked_count,
                        waiting_tasks=F("waiting_tasks") + blocked_count,
                        depend_tasks=F("depend_tasks") + blocked_count,
                    )
                    Job.objects.filter(pk=job.pk).update(
                        ready_tasks=F("ready_tasks") - blocked_count,
                        waiting_tasks=F("waiting_tasks") + blocked_count,
                        depend_tasks=F("depend_tasks") + blocked_count,
                    )
                    
            else:
                Dependency.objects.create(
                    type=DependencyType.LAYER_ON_LAYER,
                    dep_job=job,
                    dep_layer=dep_layer,
                    parent_job=job,
                    parent_layer=parent_layer,
                )
                
                blocked_task_count = Task.objects.filter(layer=dep_layer, state=TaskState.READY).update(
                    state=TaskState.WAITING,
                    depend_count=F("depend_count") + 1,
                )
                
                if blocked_task_count > 0:
                    Layer.objects.filter(pk=dep_layer.pk).update(
                        ready_tasks=F("ready_tasks") - blocked_task_count,
                        waiting_tasks=F("waiting_tasks") + blocked_task_count,
                        depend_tasks=F("depend_tasks") + blocked_task_count,
                    )
                    Job.objects.filter(pk=job.pk).update(
                        ready_tasks=F("ready_tasks") - blocked_task_count,
                        waiting_tasks=F("waiting_tasks") + blocked_task_count,
                        depend_tasks=F("depend_tasks") + blocked_task_count,
                    )
                else:
                    # Update depend_count for tasks already WAITING, but don't touch ready/waiting counters
                    Task.objects.filter(layer=dep_layer).exclude(state=TaskState.READY).update(
                        depend_count=F("depend_count") + 1
                    )

    # ── Process External Job Dependencies (JOB_ON_JOB) ───────────────────────
    if dependencies_data:
        for dep_spec in dependencies_data:
            parent_job_id = dep_spec["parent_job"]
            try:
                parent_job_obj = Job.objects.get(pk=parent_job_id)
            except Job.DoesNotExist:
                raise ValueError(f"Parent job '{parent_job_id}' does not exist.")
                
            dep_layer_name = dep_spec.get("dep_layer")
            parent_layer_name = dep_spec.get("parent_layer")
            
            d_layer = created_layers.get(dep_layer_name) if dep_layer_name else None
            p_layer = None
            if parent_layer_name:
                import uuid
                try:
                    # Attempt to parse as UUID first (e.g. from frontend LayerSelector)
                    uuid_obj = uuid.UUID(parent_layer_name)
                    p_layer = Layer.objects.filter(job=parent_job_obj, pk=uuid_obj).first()
                except ValueError:
                    # Fallback to name lookup
                    p_layer = Layer.objects.filter(job=parent_job_obj, name=parent_layer_name).first()
            
            if dep_layer_name and not d_layer:
                raise ValueError(f"Layer '{dep_layer_name}' not found on this job.")
            if parent_layer_name and not p_layer:
                raise ValueError(f"Layer '{parent_layer_name}' not found on parent job '{parent_job_id}'.")
                
            if check_dependency_cycle(job.pk, parent_job_obj.pk, "job"):
                raise ValueError("Adding this job dependency would create a cycle.")
                
            dep_type = DependencyType.LAYER_ON_LAYER if (d_layer or p_layer) else DependencyType.JOB_ON_JOB

            Dependency.objects.create(
                type=dep_type,
                dep_job=job,
                dep_layer=d_layer,
                parent_job=parent_job_obj,
                parent_layer=p_layer,
            )
            
            task_qs = Task.objects.filter(layer=d_layer) if d_layer else Task.objects.filter(job=job)
            
            # Find how many are READY (so we transition them to WAITING)
            blocked_task_count = task_qs.filter(state=TaskState.READY).update(
                state=TaskState.WAITING,
                depend_count=F("depend_count") + 1,
            )
            
            # Find the rest (already WAITING) and just increment depend_count
            task_qs.exclude(state=TaskState.READY).update(
                depend_count=F("depend_count") + 1
            )
            
            if blocked_task_count > 0:
                # Recalculate counters from Tasks to avoid negative values; safe because
                # this is inside a single atomic transaction.
                for created_layer in created_layers.values():
                    rt = Task.objects.filter(layer=created_layer, state=TaskState.READY).count()
                    wt = Task.objects.filter(layer=created_layer, state=TaskState.WAITING).count()
                    Layer.objects.filter(pk=created_layer.pk).update(
                        ready_tasks=rt,
                        waiting_tasks=wt,
                        depend_tasks=wt
                    )
                
                # And for the Job:
                jrt = Task.objects.filter(job=job, state=TaskState.READY).count()
                jwt = Task.objects.filter(job=job, state=TaskState.WAITING).count()
                Job.objects.filter(pk=job.pk).update(
                    ready_tasks=jrt,
                    waiting_tasks=jwt,
                    depend_tasks=jwt
                )

    job.refresh_from_db()
    return job
