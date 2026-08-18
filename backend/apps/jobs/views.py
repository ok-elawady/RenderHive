"""
Views for the jobs app REST API.

ViewSets follow the serializer split pattern:
- List actions use slim serializers for fast queries.
- Retrieve actions use full serializers with nested data.
- Create actions use dedicated write serializers.
- State transitions are handled by ``@action`` endpoints, not raw PATCH.
"""

import re

import django_filters
from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.workers.capabilities import extract_layer_requirements, worker_supports_layer

from .models import Dependency, Job, JobState, Layer, Task, TaskState
from .permissions import IsFarmAgent, IsJobOwnerOrStaff
from .serializers import (
    DependencyCreateSerializer,
    DependencyReadSerializer,
    JobCreateSerializer,
    JobDetailSerializer,
    JobListSerializer,
    JobPatchSerializer,
    LayerDetailSerializer,
    LayerListSerializer,
    RecentDispatchLogSerializer,
    TaskDetailSerializer,
    TaskFailSerializer,
    TaskListSerializer,
    TaskStartSerializer,
    TaskSucceedSerializer,
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
        fields = [
            "type", "is_satisfied",
            "dep_job", "parent_job",
            "dep_layer", "parent_layer",
            "dep_task", "parent_task",
        ]



from rest_framework.pagination import PageNumberPagination


class TaskPagination(PageNumberPagination):
    """Pagination for Task listing, allowing large frame ranges per layer."""

    page_size = 5000
    page_size_query_param = "page_size"
    max_page_size = 10000


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
    ordering_fields = ["priority", "created_at", "updated_at", "state", "project"]
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
        if self.action in ("partial_update", "destroy", "pause", "resume", "requeue_failed"):
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

        from apps.telemetry.models import EventSeverity
        from apps.telemetry.services import record_event

        actor = request.user.username if request.user and request.user.is_authenticated else "system"
        job_display = job.visible_name or job.name
        record_event(
            event_type="JOB_PAUSED",
            message=f"Job '{job_display}' was paused.",
            actor_username=actor,
            target_type="job",
            target_id=str(job.id),
            target_name=job_display,
            severity=EventSeverity.INFO,
        )
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

        from apps.telemetry.models import EventSeverity
        from apps.telemetry.services import record_event

        actor = request.user.username if request.user and request.user.is_authenticated else "system"
        job_display = job.visible_name or job.name
        record_event(
            event_type="JOB_RESUMED",
            message=f"Job '{job_display}' was resumed.",
            actor_username=actor,
            target_type="job",
            target_id=str(job.id),
            target_name=job_display,
            severity=EventSeverity.INFO,
        )
        return Response({"status": "resumed", "is_paused": False})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def requeue_failed(self, request, pk=None):
        """Requeue all FAILED tasks in this job back to READY state.

        Args:
            request: The HTTP request.
            pk: The Job UUID.

        Returns:
            ``200 OK`` with count of requeued tasks.
        """
        job = self.get_object()
        failed_tasks = list(
            Task.objects.select_for_update().filter(job=job, state=TaskState.FAILED)
        )
        if not failed_tasks:
            return Response({"requeued_count": 0, "status": "no_failed_tasks"})

        for task in failed_tasks:
            task.state = TaskState.READY
            task.worker_name = ""
            task.stopped_at = None
            task.started_at = None
            task.exit_status = -1
            task.max_memory_used_mb = 0
            task.save()

        # If job was FAILED, reset to RUNNING (or PENDING if no tasks currently rendering)
        if job.state == JobState.FAILED:
            job.state = JobState.RUNNING if job.running_tasks > 0 else JobState.PENDING
            job.save(update_fields=["state", "updated_at"])

        from apps.telemetry.models import EventSeverity
        from apps.telemetry.services import record_event

        actor = request.user.username if request.user and request.user.is_authenticated else "operator"
        job_display = job.visible_name or job.name
        record_event(
            event_type="JOB_REQUEUED",
            message=f"Requeued {len(failed_tasks)} failed task(s) for job '{job_display}'.",
            actor_username=actor,
            target_type="job",
            target_id=str(job.id),
            target_name=job_display,
            payload={"requeued_count": len(failed_tasks)},
            severity=EventSeverity.INFO,
        )
        return Response({"requeued_count": len(failed_tasks), "status": "requeued"})


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

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def requeue_failed(self, request, job_pk=None, pk=None):
        """Requeue all FAILED tasks in this layer back to READY state.

        Args:
            request: The HTTP request.
            job_pk: The Job UUID.
            pk: The Layer UUID.

        Returns:
            ``200 OK`` with count of requeued tasks.
        """
        layer = get_object_or_404(Layer.objects.filter(job_id=job_pk), pk=pk)
        failed_tasks = list(
            Task.objects.select_for_update().filter(layer=layer, state=TaskState.FAILED)
        )
        if not failed_tasks:
            return Response({"requeued_count": 0, "status": "no_failed_tasks"})

        for task in failed_tasks:
            task.state = TaskState.READY
            task.worker_name = ""
            task.stopped_at = None
            task.started_at = None
            task.exit_status = -1
            task.max_memory_used_mb = 0
            task.save()

        from apps.telemetry.models import EventSeverity
        from apps.telemetry.services import record_event

        actor = request.user.username if request.user and request.user.is_authenticated else "operator"
        record_event(
            event_type="LAYER_REQUEUED",
            message=f"Requeued {len(failed_tasks)} failed task(s) in layer '{layer.name}'.",
            actor_username=actor,
            target_type="layer",
            target_id=str(layer.id),
            target_name=layer.name,
            payload={"requeued_count": len(failed_tasks)},
            severity=EventSeverity.INFO,
        )
        return Response({"requeued_count": len(failed_tasks), "status": "requeued"})


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
    pagination_class = TaskPagination
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
        if self.action in ("skip", "retry"):
            return [IsAuthenticated()]
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

        # Telemetry: Record execution log for this completed attempt
        from apps.telemetry.services import record_task_log

        duration = (
            (task.stopped_at - task.started_at).total_seconds()
            if task.stopped_at and task.started_at
            else data.get("duration_seconds", 0.0)
        )
        worker_hostname = data.get("worker_hostname") or task.worker_name or "unknown"
        record_task_log(
            task=task,
            worker_hostname=worker_hostname,
            exit_status=0,
            log_output=data.get("log_output", ""),
            error_tail=data.get("error_tail", ""),
            duration_seconds=duration,
            peak_memory_mb=task.max_memory_used_mb,
            output_image_path=data.get("output_image_path", ""),
            attempt_number=task.retries + 1,
        )
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
        data = serializer.validated_data

        worker_hostname = data.get("worker_hostname") or task.worker_name or "unknown"
        task.exit_status = data["exit_status"]
        task.retries += 1

        duration = (
            (timezone.now() - task.started_at).total_seconds()
            if task.started_at
            else data.get("duration_seconds", 0.0)
        )

        from apps.telemetry.models import EventSeverity
        from apps.telemetry.services import record_event, record_task_log

        # Record telemetry log for this attempt
        record_task_log(
            task=task,
            worker_hostname=worker_hostname,
            exit_status=task.exit_status,
            log_output=data.get("log_output", ""),
            error_tail=data.get("error_tail", ""),
            duration_seconds=duration,
            peak_memory_mb=task.max_memory_used_mb,
            output_image_path=data.get("output_image_path", ""),
            attempt_number=task.retries,
        )

        job_name = task.job.name if task.job else ""
        layer_name = task.layer.name if task.layer else ""
        payload = {
            "task_id": str(task.id),
            "job_id": str(task.job_id),
            "job_name": job_name,
            "layer_id": str(task.layer_id) if task.layer_id else "",
            "layer_name": layer_name,
            "worker_hostname": worker_hostname,
            "exit_status": task.exit_status,
            "error_tail": data.get("error_tail", "")[:500] if data.get("error_tail") else "",
            "retries": task.retries,
            "max_retries": task.max_retries,
            "duration_seconds": duration,
        }

        task.state = TaskState.FAILED
        task.stopped_at = timezone.now()
        task.save()
        record_event(
            event_type="TASK_FAILED",
            message=(
                f"Task '{task.name}' failed on worker '{worker_hostname}' "
                f"(exit code {task.exit_status}, attempt #{task.retries})."
            ),
            actor_username=worker_hostname,
            target_type="task",
            target_id=str(task.id),
            target_name=task.name,
            payload=payload,
            severity=EventSeverity.ERROR,
        )
        return Response({"status": "failed"})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def retry(self, request, pk=None, **kwargs):
        """Requeue a task back to READY state (supports FAILED, SUCCEEDED, SKIPPED, RUNNING, or already READY).

        Args:
            request: HTTP request.
            pk: Task UUID.

        Returns:
            ``200 OK`` with status.
        """
        queryset = self.filter_queryset(self.get_queryset())
        task = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, task)

        prev_state = task.state
        if task.state == TaskState.WAITING:
            # If waiting on dependencies, ensure worker/timestamps are cleared
            task.worker_name = ""
            task.stopped_at = None
            task.started_at = None
            task.exit_status = -1
            task.max_memory_used_mb = 0
            task.save(update_fields=["worker_name", "stopped_at", "started_at", "exit_status", "max_memory_used_mb", "updated_at"])
            return Response({"status": "waiting", "previous_state": prev_state, "detail": "Task is waiting on dependencies."})

        task.state = TaskState.READY
        task.worker_name = ""
        task.stopped_at = None
        task.started_at = None
        task.exit_status = -1
        task.max_memory_used_mb = 0
        task.save()

        from apps.telemetry.models import EventSeverity
        from apps.telemetry.services import record_event

        actor = request.user.username if request.user and request.user.is_authenticated else "operator"
        record_event(
            event_type="TASK_REQUEUED",
            message=f"Task '{task.name}' ({prev_state}) was requeued for execution by {actor}.",
            actor_username=actor,
            target_type="task",
            target_id=str(task.id),
            target_name=task.name,
            payload={"previous_state": prev_state},
            severity=EventSeverity.INFO,
        )
        return Response({"status": "ready", "previous_state": prev_state})

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

        from apps.telemetry.models import EventSeverity
        from apps.telemetry.services import record_event

        actor = request.user.username if request.user and request.user.is_authenticated else "system"
        record_event(
            event_type="TASK_SKIPPED",
            message=f"Task '{task.name}' was skipped by supervisor {actor}.",
            actor_username=actor,
            target_type="task",
            target_id=str(task.id),
            target_name=task.name,
            severity=EventSeverity.INFO,
        )
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
    """Atomically find, lock, and dispatch a READY task to a worker.

    Scoring and AI evaluation happen OUTSIDE the DB transaction to avoid
    holding DB connections open during slow network I/O (LLM call). Only
    the final claim step (select_for_update + save) runs inside an atomic
    block, targeting just the single winning task.
    """

    permission_classes = [IsFarmAgent]
    serializer_class = TaskStartSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        worker_name = serializer.validated_data["worker_name"]

        from apps.jobs.scoring.ai_client import AIScoreAdjuster
        from apps.jobs.scoring.base import BaseScorer
        from apps.workers.models import WorkerNode, WorkerStatus

        worker = (
            WorkerNode.objects.filter(hostname=worker_name)
            .prefetch_related("pools")
            .first()
        )
        worker_pools = worker.pools.all() if worker else []

        maxed_jobs = (
            Job.objects.filter(max_tasks_per_worker__gt=0).annotate(
                active_worker_tasks=Count(
                    "tasks",
                    filter=Q(
                        tasks__state=TaskState.RUNNING,
                        tasks__worker_name=worker_name,
                    ),
                )
            )
            .filter(active_worker_tasks__gte=F("max_tasks_per_worker"))
            .values("pk")
        )

        allowed_jobs = (
            Job.objects.filter(
                is_paused=False,
                state__in=[JobState.PENDING, JobState.RUNNING],
            )
            .exclude(pk__in=maxed_jobs)
            .filter(
                Q(included_pools__isnull=True)
                | Q(included_pools__in=worker_pools)
            )
            .exclude(excluded_pools__in=worker_pools)
            .distinct()
            .values("pk")
        )

        # Build an unordered, unlocked queryset — we do NOT lock the full batch.
        # select_related and prefetch_related ensure BaseScorer can access task.job,
        # task.layer, and historical execution_logs without additional queries.
        candidates_qs = (
            Task.objects.select_related("layer", "job")
            .prefetch_related("execution_logs")
            .filter(state=TaskState.READY, job_id__in=allowed_jobs)
        )

        # Resource filtering in SQL — hard constraints only.
        # DCC / version / execution compatibility is checked in Python below.
        if worker is not None:
            candidates_qs = candidates_qs.filter(
                layer__min_cores__lte=max(int(worker.cores or 1), 1),
                layer__min_memory_mb__lte=max(int(worker.memory_mb or 1), 1),
                layer__min_gpus__lte=len(worker.gpu_models or []),
            )

        # Fetch the top 200 candidates for scoring, ordered deterministically.
        candidates_list = list(
            candidates_qs.order_by("-job__priority", "dispatch_order")[:200]
        )

        if not candidates_list:
            return Response(
                {"detail": "No compatible tasks available."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Phase 1: Deterministic Base Scoring (no DB lock held) ────────────
        scored_tasks = BaseScorer().score(worker, candidates_list)

        # DCC / version / execution capability check in Python.
        supported_tasks = [
            ts for ts in scored_tasks
            if worker_supports_layer(worker, ts.task.layer)[0]
        ]

        if not supported_tasks:
            return Response(
                {"detail": "No compatible tasks available after capability filtering."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Phase 2: AI Tie-Breaker (outside transaction — may make HTTP call) ─
        top_score = supported_tasks[0].base_score
        # Use a RELATIVE threshold (10% of the top score) rather than an absolute
        # value. An absolute threshold of 0.05 would incorrectly invoke the AI for
        # every dispatch on farms where all jobs share the same priority, because all
        # base scores cluster tightly around the same value regardless of absolute
        # magnitude. The relative threshold correctly captures genuine ties.
        tie_threshold = max(top_score * 0.10, 0.005)  # floor of 0.005 handles near-zero scores
        competitive_tasks = [
            ts for ts in supported_tasks if (top_score - ts.base_score) <= tie_threshold
        ]

        if len(competitive_tasks) > 1 and getattr(settings, "SCHEDULER_AI_ENABLED", True):
            capabilities_snapshot = request.data.get("capabilities_snapshot")
            adjusted = AIScoreAdjuster(worker).adjust(competitive_tasks, capabilities_snapshot)
            best = adjusted[0]
        else:
            best = competitive_tasks[0]

        winner_id = best.task.id
        final_score_breakdown = best.score_breakdown

        # ── Phase 3: Atomic claim — lock ONLY the winning task row ──────────
        with transaction.atomic():
            task = (
                Task.objects.select_for_update(skip_locked=True)
                .filter(pk=winner_id, state=TaskState.READY)
                .first()
            )
            if task is None:
                # Another worker claimed this task between scoring and claiming.
                return Response(
                    {"detail": "Task was claimed concurrently. Retry dispatch."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            task.state = TaskState.RUNNING
            task.worker_name = worker_name
            task.started_at = timezone.now()
            task.last_score_breakdown = final_score_breakdown
            task.save(
                update_fields=[
                    "state",
                    "worker_name",
                    "started_at",
                    "updated_at",
                    "last_score_breakdown",
                ]
            )

            if worker is not None:
                WorkerNode.objects.filter(pk=worker.pk).update(
                    status=WorkerStatus.RENDERING,
                    last_ping=timezone.now(),
                )

        layer = task.layer
        job = task.job

        # Telemetry: Record historical dispatch trace for observability
        from apps.telemetry.services import record_dispatch_trace

        ai_reason_str = str((final_score_breakdown or {}).get("ai_reason", ""))
        is_mock_ai = "mock" in ai_reason_str.lower() or "only one candidate" in ai_reason_str.lower()
        has_real_ai = bool(
            final_score_breakdown
            and "ai_adjustment" in final_score_breakdown
            and not is_mock_ai
        )

        record_dispatch_trace(
            task=task,
            job=job,
            worker_hostname=worker_name,
            candidate_count=len(supported_tasks),
            ai_invoked=has_real_ai,
            ai_latency_ms=getattr(best, "ai_latency_ms", None) if has_real_ai else None,
            ai_reason=ai_reason_str,
            score_breakdown=final_score_breakdown,
        )
        scene_info = layer.scene_info if isinstance(layer.scene_info, dict) else {}
        execution = scene_info.get("execution")
        if not isinstance(execution, dict):
            execution = {}
        env = layer.env if isinstance(layer.env, dict) else {}
        requirements = extract_layer_requirements(layer)

        # Extract the frame step from the range string if it is uniform across all
        # segments. Mixed-step ranges (e.g. "1-50x2,51-100x5") fall back to 1 so
        # the worker processes every frame in the chunk independently.
        frame_step = 1
        step_matches = {
            int(value)
            for value in re.findall(r"x(\d+)", str(layer.frame_range or ""))
            if int(value) > 0
        }
        if len(step_matches) == 1:
            frame_step = next(iter(step_matches))

        dcc = requirements["dcc"]
        dcc_version = requirements["dcc_version"]
        renderer = requirements["renderer"]
        render_node = str(
            scene_info.get("render_node")
            or execution.get("render_node")
            or ""
        )
        camera = str(
            scene_info.get("camera")
            or execution.get("camera")
            or ""
        )
        execution_mode = str(
            requirements["execution_mode"]
            or ("hython" if dcc == "houdini" else "render")
        ).lower()
        output_path = str(
            scene_info.get("output_path")
            or execution.get("output_path")
            or ""
        )
        project_path = str(
            scene_info.get("project_path")
            or env.get("JOB")
            or ""
        )
        usd_output_path = str(
            execution.get("usd_output_path")
            or scene_info.get("usd_output_path")
            or ""
        )

        return Response(
            {
                # Legacy flat fields
                "id": str(task.id),
                "name": task.name,
                "frame_start": task.frame_start,
                "frame_end": task.frame_end,
                "frame_step": frame_step,
                "job_id": str(task.job_id),
                "layer_id": str(task.layer_id),
                "command": layer.command,
                "scene_path": layer.scene_path,
                "env": env,
                "chunk_size": layer.chunk_size,
                # Multi-DCC fields consumed by Worker 1.1+
                "dcc": dcc,
                "dcc_version": dcc_version,
                "renderer": renderer,
                "render_node": render_node,
                "camera": camera,
                "execution_mode": execution_mode,
                "output_path": output_path,
                "project_path": project_path,
                "usd_output_path": usd_output_path,
                "scene_info": scene_info,
                "execution": execution,
                "frames": {
                    "start": task.frame_start,
                    "end": task.frame_end,
                    "step": frame_step,
                },
                "layer": {
                    "id": str(layer.id),
                    "name": layer.name,
                    "command": layer.command,
                    "scene_path": layer.scene_path,
                    "scene_info": scene_info,
                    "env": env,
                    "chunk_size": layer.chunk_size,
                    "min_cores": layer.min_cores,
                    "min_memory_mb": layer.min_memory_mb,
                    "min_gpus": layer.min_gpus,
                    "tags": list(layer.tags or []),
                    "timeout_seconds": layer.timeout_seconds,
                    "max_retries": layer.max_retries,
                },
                "job": {
                    "id": str(job.id),
                    "name": job.name,
                    "visible_name": job.visible_name,
                    "project": job.project,
                    "department": job.department,
                    "priority": job.priority,
                },
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


# ── Recent Dispatches View ────────────────────────────────────────────────────


@extend_schema(
    summary="Get recent task dispatches",
    description="Return the most recently dispatched tasks with their AI score breakdowns.",
    parameters=[
        OpenApiParameter(
            name="limit",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Number of tasks to return (default 30, max 100).",
            default=30,
        )
    ],
    responses={200: RecentDispatchLogSerializer(many=True)},
)
class RecentDispatchesView(generics.GenericAPIView):
    """Return the most recently dispatched tasks with their AI score breakdowns."""

    permission_classes = [IsAuthenticated]
    serializer_class = RecentDispatchLogSerializer

    def get(self, request, *args, **kwargs):
        """Return recently dispatched tasks with their score breakdowns.

        Args:
            request: The HTTP request.

        Returns:
            A list of recently dispatched task summaries.
        """
        try:
            limit = min(int(request.query_params.get("limit", 30)), 100)
        except (ValueError, TypeError):
            limit = 30

        tasks = (
            Task.objects.select_related("job", "layer")
            .exclude(last_score_breakdown__isnull=True)
            .exclude(worker_name__isnull=True)
            .order_by("-started_at")[:limit]
        )

        results = []
        for task in tasks:
            breakdown = task.last_score_breakdown or {}
            results.append({
                "id": str(task.id),
                "name": task.name,
                "worker_name": task.worker_name,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "state": task.state,
                "job_id": str(task.job_id),
                "job_name": task.job.visible_name or task.job.name,
                "job_priority": task.job.priority,
                "layer_name": task.layer.name,
                "last_score_breakdown": breakdown,
                # Convenience top-level fields derived from the breakdown
                "ai_was_invoked": "ai_adjustment" in breakdown,
                "ai_reason": breakdown.get("ai_reason", ""),
                "final_score": (
                    breakdown.get("job_priority", 0)
                    + breakdown.get("resource_fit", 0)
                    + breakdown.get("failure_penalty", 0)
                    + breakdown.get("dispatch_order", 0)
                    + breakdown.get("_floor_clamp", 0)
                    + breakdown.get("ai_adjustment", 0)
                ),
            })

        return Response(results)

