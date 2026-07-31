"""
Views for the jobs app REST API.

ViewSets follow the serializer split pattern:
- List actions use slim serializers for fast queries.
- Retrieve actions use full serializers with nested data.
- Create actions use dedicated write serializers.
- State transitions are handled by ``@action`` endpoints, not raw PATCH.
"""

import django_filters
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Dependency, Task, TaskState, Job, JobState, Layer
from .permissions import IsFarmAgent, IsJobOwnerOrStaff
from .serializers import (
    DependencyCreateSerializer,
    DependencyReadSerializer,
    TaskDetailSerializer,
    TaskFailSerializer,
    TaskListSerializer,
    TaskStartSerializer,
    TaskSucceedSerializer,
    JobCreateSerializer,
    JobDetailSerializer,
    JobListSerializer,
    JobPatchSerializer,
    LayerDetailSerializer,
    LayerListSerializer,
)

# ── Filters ───────────────────────────────────────────────────────────────────


class JobFilter(django_filters.FilterSet):
    """FilterSet for the Job list endpoint.

    Allows filtering by state, project, department, and user via query params.
    Example: ``GET /api/jobs/?state=RUNNING&project=proj_x``

    Attributes:
        state: Filter by job state (e.g. ``PENDING``, ``RUNNING``).
        project: Exact match on project field.
        department: Exact match on department field.
        user: Exact match on user field.
    """

    project = django_filters.CharFilter(lookup_expr="icontains")
    department = django_filters.CharFilter(lookup_expr="icontains")
    user = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Job
        fields = ["state", "project", "department", "user"]

class DependencyFilter(django_filters.FilterSet):
    """FilterSet for the Dependency list endpoint.

    Allows filtering by type, satisfaction status, and the key entity FKs.
    Example: ``GET /api/dependencies/?dep_job=<uuid>&is_satisfied=false``

    Attributes:
        type: Filter by dependency type (TASK_ON_TASK, LAYER_ON_LAYER, JOB_ON_JOB).
        is_satisfied: Filter by satisfaction status.
        dep_job: Filter by the blocked job's UUID.
        parent_job: Filter by the blocking job's UUID.
        dep_layer: Filter by the blocked layer's UUID.
        parent_layer: Filter by the blocking layer's UUID.
        dep_task: Filter by the blocked task's UUID.
        parent_task: Filter by the blocking task's UUID.
    """

    class Meta:
        model = Dependency
        fields = ["type", "is_satisfied", "dep_job", "parent_job", "dep_layer", "parent_layer", "dep_task", "parent_task"]



class TaskFilter(django_filters.FilterSet):
    """FilterSet for the Task list endpoint.

    Allows filtering by state via query params.
    Example: ``GET /api/jobs/{id}/layers/{id}/tasks/?state=FAILED``

    Attributes:
        state: Filter by task state (e.g. ``READY``, ``FAILED``).
    """

    class Meta:
        model = Task
        fields = ["state"]


# ── Job ViewSet ───────────────────────────────────────────────────────────────


class JobViewSet(viewsets.ModelViewSet):
    """ViewSet for listing, submitting, updating, and deleting jobs.

    Endpoints:
        ``GET    /api/jobs/``         — list all jobs, supports filtering.
        ``POST   /api/jobs/``         — submit a new job with nested layers.
        ``GET    /api/jobs/{id}/``    — retrieve full job detail with layers.
        ``PATCH  /api/jobs/{id}/``    — update priority or visible_name.
        ``DELETE /api/jobs/{id}/``    — delete a job and all its layers/tasks.
        ``POST   /api/jobs/{id}/pause/``  — pause the job.
        ``POST   /api/jobs/{id}/resume/`` — resume a paused job.
    """

    queryset = Job.objects.all().order_by("-priority", "created_at")
    filterset_class = JobFilter
    ordering_fields = ["priority", "created_at", "updated_at", "state"]
    search_fields = ["name", "visible_name", "user", "project", "department"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """Return the base queryset, optimized with prefetches for retrieve and list.

        Pool M2M relations are prefetched for both list and retrieve to avoid
        N+1 queries — each job in a list would otherwise trigger 2 extra SQL
        queries (one per pool relation) without prefetching.
        """
        qs = super().get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related("layers", "included_pools", "excluded_pools")
        elif self.action == "list":
            qs = qs.prefetch_related("included_pools", "excluded_pools")
        return qs

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action.

        Returns:
            A serializer class matched to the current action.
        """
        if self.action == "list":
            return JobListSerializer
        if self.action == "create":
            return JobCreateSerializer
        if self.action == "partial_update":
            return JobPatchSerializer
        return JobDetailSerializer

    def get_permissions(self):
        """Return per-action permission classes.

        Returns:
            A list of instantiated permission objects for the current action.
        """
        if self.action in ("partial_update", "destroy", "pause", "resume"):
            return [IsAuthenticated(), IsJobOwnerOrStaff()]
        return [IsAuthenticated()]

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        """Pause a job, preventing new tasks from being dispatched.

        Sets ``is_paused=True`` on the job. Does not terminate currently
        running tasks — they will complete their current render.

        Args:
            request: The HTTP request.
            pk: The Job UUID.

        Returns:
            A ``200 OK`` response with the updated job state.
        """
        job = self.get_object()
        job.is_paused = True
        job.state = JobState.PAUSED
        job.save(update_fields=["is_paused", "state", "updated_at"])
        return Response({"status": "paused", "is_paused": True})

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        """Resume a paused job, allowing tasks to be dispatched again.

        Sets ``is_paused=False`` on the job.

        Args:
            request: The HTTP request.
            pk: The Job UUID.

        Returns:
            A ``200 OK`` response with the updated job state.
        """
        job = self.get_object()
        job.is_paused = False

        # Recalculate state based on current counters
        if job.running_tasks > 0:
            job.state = JobState.RUNNING
        elif job.total_tasks > 0 and (job.succeeded_tasks + job.skipped_tasks) == job.total_tasks:
            job.state = JobState.FINISHED
        elif job.failed_tasks > 0 and job.ready_tasks == 0 and job.running_tasks == 0:
            job.state = JobState.FAILED
        else:
            job.state = JobState.PENDING

        job.save(update_fields=["is_paused", "state", "updated_at"])
        return Response({"status": "resumed", "is_paused": False})


# ── Layer ViewSet ─────────────────────────────────────────────────────────────


class LayerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only ViewSet for listing and retrieving layers scoped to a job.

    Endpoints (nested under /api/jobs/{job_pk}/):
        ``GET  /api/jobs/{job_pk}/layers/``         — list all layers for a job.
        ``GET  /api/jobs/{job_pk}/layers/{id}/``    — retrieve a single layer.

    All endpoints require authentication. Layers are scoped to the parent job
    via the ``job_pk`` URL kwarg.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return layers scoped to the parent job.

        Returns:
            A queryset of Layer objects for the job specified by ``job_pk``.
        """
        return Layer.objects.filter(job_id=self.kwargs["job_pk"])

    def get_serializer_class(self):
        """Return slim serializer for list, full serializer for detail.

        Returns:
            A serializer class matched to the current action.
        """
        if self.action == "list":
            return LayerListSerializer
        return LayerDetailSerializer


# ── Task ViewSet ─────────────────────────────────────────────────────────────


class TaskViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """ViewSet for listing tasks and handling Worker state transition actions.

    List/retrieve endpoints are nested under a layer:
        ``GET  /api/jobs/{job_pk}/layers/{layer_pk}/tasks/``
        ``GET  /api/jobs/{job_pk}/layers/{layer_pk}/tasks/{id}/``

    State transition action endpoints are on the top-level ``/api/tasks/``
    router, identified by UUID only (no nesting required for Workers):
        ``POST /api/tasks/{id}/start/``
        ``POST /api/tasks/{id}/succeed/``
        ``POST /api/tasks/{id}/fail/``
        ``POST /api/tasks/{id}/skip/``
        ``POST /api/tasks/{id}/checkpoint/``
    """

    filterset_class = TaskFilter
    search_fields = ["name", "worker_name", "layer__job__name", "layer__job__visible_name"]

    def get_queryset(self):
        """Return tasks, optionally scoped to a parent layer.

        When called from the nested router (layer context), filters by
        ``layer_pk``. When called from the top-level router (Worker actions),
        returns all tasks.

        Returns:
            A queryset of Task objects.
        """
        layer_pk = self.kwargs.get("layer_pk")
        if layer_pk:
            return Task.objects.filter(layer_id=layer_pk)
        return Task.objects.all()

    def get_serializer_class(self):
        """Return the appropriate serializer for the current action.

        Returns:
            A serializer class matched to the current action.
        """
        if self.action == "list":
            return TaskListSerializer
        if self.action == "start":
            return TaskStartSerializer
        if self.action == "succeed":
            return TaskSucceedSerializer
        if self.action == "fail":
            return TaskFailSerializer
        return TaskDetailSerializer

    def get_permissions(self):
        """Return per-action permission classes.

        Worker actions require ``IsFarmAgent`` permission. The ``skip`` action
        requires staff status. All other actions require basic authentication.

        Returns:
            A list of instantiated permission objects for the current action.
        """
        if self.action in ("start", "succeed", "fail", "checkpoint"):
            return [IsFarmAgent()]
        if self.action == "skip":
            return [IsAuthenticated()]  # View enforces is_staff internally
        return [IsAuthenticated()]

    @action(detail=True, methods=["post"], serializer_class=TaskStartSerializer)
    @transaction.atomic
    def start(self, request, pk=None, **kwargs):
        """Mark a task as RUNNING when a Worker begins execution.

        Records the Worker hostname and execution start timestamp. Only
        valid when the task is in ``READY`` state.

        Args:
            request: HTTP request containing ``worker_name``.
            pk: Task UUID.

        Returns:
            ``200 OK`` on success.
            ``409 Conflict`` if the task is not in READY state.
        """
        queryset = self.filter_queryset(self.get_queryset())
        task = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, task)
        if task.state != TaskState.READY:
            return Response(
                {"detail": f"Cannot start a task in state '{task.state}'."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task.state = TaskState.RUNNING
        task.worker_name = serializer.validated_data["worker_name"]
        task.started_at = timezone.now()
        task.save(update_fields=["state", "worker_name", "started_at", "updated_at"])
        return Response({"status": "running"})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def succeed(self, request, pk=None, **kwargs):
        """Mark a task as SUCCEEDED and record telemetry.

        Transitions state, logs exit code and stop timestamp.
        Returns 409 if the task isn't currently running/checkpointing.
        """
        queryset = self.filter_queryset(self.get_queryset())
        task = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, task)
        if task.state not in (TaskState.RUNNING, TaskState.CHECKPOINT):
            return Response(
                {"detail": f"Cannot succeed a task in state '{task.state}'."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        task.state = TaskState.SUCCEEDED
        task.exit_status = data["exit_status"]
        task.max_memory_used_mb = data["max_memory_used_mb"]
        if data.get("cores_used") is not None:
            task.cores_used = data["cores_used"]
        # stopped_at is set by the task_pre_save signal on SUCCEEDED/SKIPPED transitions.
        task.save()
        return Response({"status": "succeeded"})

    @action(detail=True, methods=["post"], serializer_class=TaskFailSerializer)
    @transaction.atomic
    def fail(self, request, pk=None, **kwargs):
        """Mark a task as FAILED or retry it based on the retry budget.

        Increments the retry counter. If ``retries >= max_retries``, the task
        transitions to ``FAILED`` permanently. Otherwise it reverts to ``READY``
        for re-dispatch.

        Args:
            request: HTTP request containing ``exit_status``.
            pk: Task UUID.

        Returns:
            ``200 OK`` with the resulting state (``failed`` or ``retrying``).
            ``409 Conflict`` if the task is not in RUNNING or CHECKPOINT state.
        """
        queryset = self.filter_queryset(self.get_queryset())
        task = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, task)
        if task.state not in (TaskState.RUNNING, TaskState.CHECKPOINT):
            return Response(
                {"detail": f"Cannot fail a task in state '{task.state}'."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task.exit_status = serializer.validated_data["exit_status"]
        task.retries += 1

        if task.retries >= task.max_retries:
            task.state = TaskState.FAILED
            task.stopped_at = timezone.now()
            task.save()
            return Response({"status": "failed"})
        else:
            # Task will be re-dispatched; stopped_at is intentionally not set
            # so it doesn't show a misleading end timestamp for a task still in flight.
            task.state = TaskState.READY
            task.save()
            return Response({"status": "retrying", "retries": task.retries})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def skip(self, request, pk=None, **kwargs):
        """Dismiss a failed task, allowing its dependents to proceed.

        Only available to staff users. Sets the task state to ``SKIPPED``,
        which (via signals) satisfies any dependencies blocked on this task.

        Args:
            request: HTTP request.
            pk: Task UUID.

        Returns:
            ``200 OK`` on success.
            ``403 Forbidden`` if the requesting user is not staff.
            ``409 Conflict`` if the task is not in FAILED state.
        """
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {"detail": "Only staff or superusers can skip tasks."},
                status=status.HTTP_403_FORBIDDEN,
            )
        queryset = self.filter_queryset(self.get_queryset())
        task = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, task)
        if task.state != TaskState.FAILED:
            return Response(
                {"detail": f"Only FAILED tasks can be skipped (current state: '{task.state}')."},
                status=status.HTTP_409_CONFLICT,
            )
        task.state = TaskState.SKIPPED
        task.save()
        return Response({"status": "skipped"})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def checkpoint(self, request, pk=None, **kwargs):
        """Increment the checkpoint counter for a task in progress.

        Called by a Worker when it saves a resume checkpoint (e.g. a V-Ray
        ``.vrimg`` file). The task transitions to ``CHECKPOINT`` state to
        indicate that progress has been persisted.

        Args:
            request: HTTP request.
            pk: Task UUID.

        Returns:
            ``200 OK`` with the new checkpoint count.
            ``409 Conflict`` if the task is not in RUNNING or CHECKPOINT state.
        """
        queryset = self.filter_queryset(self.get_queryset())
        task = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, task)
        if task.state not in (TaskState.RUNNING, TaskState.CHECKPOINT):
            return Response(
                {"detail": f"Cannot checkpoint a task in state '{task.state}'."},
                status=status.HTTP_409_CONFLICT,
            )

        task.checkpoint_count += 1
        task.state = TaskState.CHECKPOINT
        task.save(update_fields=["checkpoint_count", "state", "updated_at"])
        return Response({"status": "checkpointed", "checkpoint_count": task.checkpoint_count})


class TaskDispatchView(generics.GenericAPIView):
    """Atomically find, lock, and dispatch a READY task to a worker."""

    permission_classes = [IsFarmAgent]
    serializer_class = TaskStartSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # Validate worker_name using standard DRF serializer workflow
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        worker_name = serializer.validated_data["worker_name"]

        # Find the worker. If the worker is not yet registered in WorkerNode (e.g. it
        # hasn't sent a ping yet), worker_pools will be an empty list []. In that case:
        #   - Q(included_pools__in=[])  → always FALSE  → restricted jobs are skipped
        #   - Q(included_pools__isnull=True) → unrestricted jobs are still eligible
        # This means unregistered workers can only pull unrestricted jobs, which is the
        # correct and intentional behaviour — but it is implicit, hence this comment.
        from apps.workers.models import WorkerNode

        worker = WorkerNode.objects.filter(hostname=worker_name).prefetch_related("pools").first()
        worker_pools = worker.pools.all() if worker else []

        # Find jobs where this worker has reached the concurrency limit
        maxed_jobs = (
            Job.objects.annotate(
                active_worker_tasks=Count(
                    "tasks", filter=Q(tasks__state=TaskState.RUNNING, tasks__worker_name=worker_name)
                )
            )
            .filter(active_worker_tasks__gte=F("max_tasks_per_worker"))
            .values("pk")
        )

        # Determine which jobs are eligible based on state, pause flag, concurrency
        # limit, and pool routing.
        # Notes:
        #   - `state__in` is defense-in-depth: FINISHED/FAILED jobs have no READY
        #     tasks anyway, but filtering here keeps the subquery semantically clean.
        #   - `.distinct()` prevents duplicate PKs caused by the M2M JOIN when a job
        #     belongs to multiple pools that all match the worker's pools.
        allowed_jobs = (
            Job.objects.filter(
                is_paused=False,
                state__in=[JobState.PENDING, JobState.RUNNING],
            )
            .exclude(pk__in=maxed_jobs)
            .filter(Q(included_pools__isnull=True) | Q(included_pools__in=worker_pools))
            .exclude(excluded_pools__in=worker_pools)
            .distinct()
            .values("pk")
        )

        # Find the highest priority READY task and lock it
        task = (
            Task.objects.select_for_update(skip_locked=True)
            .filter(state=TaskState.READY, job_id__in=allowed_jobs)
            .order_by("job__priority", "dispatch_order")
            .first()
        )

        if not task:
            return Response({"detail": "No tasks available."}, status=status.HTTP_404_NOT_FOUND)

        # Transition task to RUNNING
        task.state = TaskState.RUNNING
        task.worker_name = worker_name
        task.started_at = timezone.now()
        task.save(update_fields=["state", "worker_name", "started_at", "updated_at"])

        # Update worker status to RENDERING
        try:
            from apps.workers.models import WorkerNode, WorkerStatus

            WorkerNode.objects.filter(hostname=worker_name).update(
                status=WorkerStatus.RENDERING, last_ping=timezone.now()
            )
        except Exception:
            pass  # If worker app is not setup yet, just pass

        # Return consolidated payload
        return Response(
            {
                "id": str(task.id),
                "name": task.name,
                "frame_start": task.frame_start,
                "frame_end": task.frame_end,
                "job_id": str(task.job_id),
                "layer_id": str(task.layer_id),
                "command": task.layer.command,
                "scene_path": task.layer.scene_path,
                "env": task.layer.env,
                "chunk_size": task.layer.chunk_size,
            }
        )


# ── Dependency ViewSet ────────────────────────────────────────────────────────


class DependencyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """ViewSet for listing, retrieving, creating, and deleting dependencies.

    Endpoints:
        ``GET    /api/dependencies/``       — list all deps, supports filtering.
        ``POST   /api/dependencies/``       — create a new dependency.
        ``GET    /api/dependencies/{id}/``  — retrieve a single dependency.
        ``DELETE /api/dependencies/{id}/``  — delete a dependency.

        Read-only nested list under jobs:
        ``GET    /api/jobs/{job_pk}/dependencies/``

    All actions require authentication. Delete is restricted to staff and
    superusers to prevent accidental removal of live dependency edges.

    The pre_delete signal on Dependency automatically repairs ``depend_count``
    and ``depend_tasks`` counters when a dependency is destroyed.
    """

    queryset = Dependency.objects.all().select_related(
        "dep_job", "dep_layer", "dep_task", "parent_job", "parent_layer", "parent_task"
    ).order_by("-created_at")
    filterset_class = DependencyFilter
    ordering_fields = ["created_at", "satisfied_at", "type", "is_satisfied"]

    def get_queryset(self):
        """Return dependencies, optionally scoped to a parent job.

        When called from the nested router (job context), filters to deps
        where the blocked entity belongs to that job.

        Returns:
            A queryset of Dependency objects.
        """
        qs = super().get_queryset()
        job_pk = self.kwargs.get("job_pk")
        if job_pk:
            from django.db.models import Q
            qs = qs.filter(Q(dep_job_id=job_pk) | Q(parent_job_id=job_pk))
        return qs

    def get_serializer_class(self):
        """Return read serializer for safe methods, write serializer for create.

        Returns:
            A serializer class matched to the current action.
        """
        if self.action == "create":
            return DependencyCreateSerializer
        return DependencyReadSerializer

    def create(self, request, *args, **kwargs):
        """Create a dependency and return the full read representation.

        Validates with DependencyCreateSerializer (which runs cycle detection),
        saves the instance, then serializes the response with DependencyReadSerializer
        so the caller receives all fields including is_satisfied and timestamps.

        Returns:
            ``201 Created`` with the full dependency representation.
        """
        write_serializer = DependencyCreateSerializer(data=request.data, context=self.get_serializer_context())
        write_serializer.is_valid(raise_exception=True)
        instance = write_serializer.save()
        read_serializer = DependencyReadSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def get_permissions(self):
        """Return per-action permission classes.

        Destroy is staff-only. All other actions require basic authentication.

        Returns:
            A list of instantiated permission objects for the current action.
        """
        return [IsAuthenticated()]

    def perform_destroy(self, instance):
        """Delete a dependency, restricted to staff and superusers.

        Args:
            instance: The Dependency to delete.

        Raises:
            PermissionDenied: If the user is not staff or superuser.
        """
        from rest_framework.exceptions import PermissionDenied

        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise PermissionDenied("Only staff or superusers can delete dependencies.")
        instance.delete()  # pre_delete signal repairs counters
