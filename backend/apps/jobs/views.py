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
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Frame, FrameState, Job, Layer
from .permissions import IsFarmAgent, IsJobOwnerOrStaff
from .serializers import (
    FrameDetailSerializer,
    FrameFailSerializer,
    FrameListSerializer,
    FrameStartSerializer,
    FrameSucceedSerializer,
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

    class Meta:
        model = Job
        fields = ["state", "project", "department", "user"]


class FrameFilter(django_filters.FilterSet):
    """FilterSet for the Frame list endpoint.

    Allows filtering by state via query params.
    Example: ``GET /api/jobs/{id}/layers/{id}/frames/?state=FAILED``

    Attributes:
        state: Filter by frame state (e.g. ``READY``, ``FAILED``).
    """

    class Meta:
        model = Frame
        fields = ["state"]


# ── Job ViewSet ───────────────────────────────────────────────────────────────


class JobViewSet(viewsets.ModelViewSet):
    """ViewSet for listing, submitting, updating, and deleting jobs.

    Endpoints:
        ``GET    /api/jobs/``         — list all jobs, supports filtering.
        ``POST   /api/jobs/``         — submit a new job with nested layers.
        ``GET    /api/jobs/{id}/``    — retrieve full job detail with layers.
        ``PATCH  /api/jobs/{id}/``    — update priority or visible_name.
        ``DELETE /api/jobs/{id}/``    — delete a job and all its layers/frames.
        ``POST   /api/jobs/{id}/pause/``  — pause the job.
        ``POST   /api/jobs/{id}/resume/`` — resume a paused job.
    """

    queryset = Job.objects.all().order_by("-priority", "created_at")
    filterset_class = JobFilter
    ordering_fields = ["priority", "created_at", "updated_at", "state"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """Return the base queryset, optimized with prefetches for retrieve."""
        qs = super().get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related("layers")
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
        """Pause a job, preventing new frames from being dispatched.

        Sets ``is_paused=True`` on the job. Does not terminate currently
        running frames — they will complete their current render.

        Args:
            request: The HTTP request.
            pk: The Job UUID.

        Returns:
            A ``200 OK`` response with the updated job state.
        """
        job = self.get_object()
        job.is_paused = True
        job.save(update_fields=["is_paused", "updated_at"])
        return Response({"status": "paused", "is_paused": True})

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        """Resume a paused job, allowing frames to be dispatched again.

        Sets ``is_paused=False`` on the job.

        Args:
            request: The HTTP request.
            pk: The Job UUID.

        Returns:
            A ``200 OK`` response with the updated job state.
        """
        job = self.get_object()
        job.is_paused = False
        job.save(update_fields=["is_paused", "updated_at"])
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


# ── Frame ViewSet ─────────────────────────────────────────────────────────────


class FrameViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """ViewSet for listing frames and handling Worker state transition actions.

    List/retrieve endpoints are nested under a layer:
        ``GET  /api/jobs/{job_pk}/layers/{layer_pk}/frames/``
        ``GET  /api/jobs/{job_pk}/layers/{layer_pk}/frames/{id}/``

    State transition action endpoints are on the top-level ``/api/frames/``
    router, identified by UUID only (no nesting required for Workers):
        ``POST /api/frames/{id}/start/``
        ``POST /api/frames/{id}/succeed/``
        ``POST /api/frames/{id}/fail/``
        ``POST /api/frames/{id}/skip/``
        ``POST /api/frames/{id}/checkpoint/``
    """

    filterset_class = FrameFilter

    def get_queryset(self):
        """Return frames, optionally scoped to a parent layer.

        When called from the nested router (layer context), filters by
        ``layer_pk``. When called from the top-level router (Worker actions),
        returns all frames.

        Returns:
            A queryset of Frame objects.
        """
        layer_pk = self.kwargs.get("layer_pk")
        if layer_pk:
            return Frame.objects.filter(layer_id=layer_pk)
        return Frame.objects.all()

    def get_serializer_class(self):
        """Return the appropriate serializer for the current action.

        Returns:
            A serializer class matched to the current action.
        """
        if self.action == "list":
            return FrameListSerializer
        if self.action == "start":
            return FrameStartSerializer
        if self.action == "succeed":
            return FrameSucceedSerializer
        if self.action == "fail":
            return FrameFailSerializer
        return FrameDetailSerializer

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

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def start(self, request, pk=None, **kwargs):
        """Mark a frame as RUNNING when a Worker begins execution.

        Records the Worker hostname and execution start timestamp. Only
        valid when the frame is in ``READY`` state.

        Args:
            request: HTTP request containing ``worker_name``.
            pk: Frame UUID.

        Returns:
            ``200 OK`` on success.
            ``409 Conflict`` if the frame is not in READY state.
        """
        queryset = self.filter_queryset(self.get_queryset())
        frame = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, frame)
        if frame.state != FrameState.READY:
            return Response(
                {"detail": f"Cannot start a frame in state '{frame.state}'."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = FrameStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        frame.state = FrameState.RUNNING
        frame.worker_name = serializer.validated_data["worker_name"]
        frame.started_at = timezone.now()
        frame.save(update_fields=["state", "worker_name", "started_at", "updated_at"])
        return Response({"status": "running"})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def succeed(self, request, pk=None, **kwargs):
        """Mark a frame as SUCCEEDED and record telemetry.

        Records exit code, peak memory, and core usage. Signals handle
        updating the parent Layer and Job counters and satisfying any
        downstream dependencies.

        Args:
            request: HTTP request containing telemetry data.
            pk: Frame UUID.

        Returns:
            ``200 OK`` on success.
            ``409 Conflict`` if the frame is not in RUNNING or CHECKPOINT state.
        """
        queryset = self.filter_queryset(self.get_queryset())
        frame = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, frame)
        if frame.state not in (FrameState.RUNNING, FrameState.CHECKPOINT):
            return Response(
                {"detail": f"Cannot succeed a frame in state '{frame.state}'."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = FrameSucceedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        frame.state = FrameState.SUCCEEDED
        frame.exit_status = data["exit_status"]
        frame.max_memory_used_mb = data["max_memory_used_mb"]
        if data.get("cores_used") is not None:
            frame.cores_used = data["cores_used"]
        frame.stopped_at = timezone.now()
        frame.save()
        return Response({"status": "succeeded"})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def fail(self, request, pk=None, **kwargs):
        """Mark a frame as FAILED or retry it based on the retry budget.

        Increments the retry counter. If ``retries >= max_retries``, the frame
        transitions to ``FAILED`` permanently. Otherwise it reverts to ``READY``
        for re-dispatch.

        Args:
            request: HTTP request containing ``exit_status``.
            pk: Frame UUID.

        Returns:
            ``200 OK`` with the resulting state (``failed`` or ``retrying``).
            ``409 Conflict`` if the frame is not in RUNNING or CHECKPOINT state.
        """
        queryset = self.filter_queryset(self.get_queryset())
        frame = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, frame)
        if frame.state not in (FrameState.RUNNING, FrameState.CHECKPOINT):
            return Response(
                {"detail": f"Cannot fail a frame in state '{frame.state}'."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = FrameFailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        frame.exit_status = serializer.validated_data["exit_status"]
        frame.retries += 1
        frame.stopped_at = timezone.now()

        if frame.retries >= frame.max_retries:
            frame.state = FrameState.FAILED
            frame.save()
            return Response({"status": "failed"})
        else:
            frame.state = FrameState.READY
            frame.save()
            return Response({"status": "retrying", "retries": frame.retries})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def skip(self, request, pk=None, **kwargs):
        """Dismiss a failed frame, allowing its dependents to proceed.

        Only available to staff users. Sets the frame state to ``SKIPPED``,
        which (via signals) satisfies any dependencies blocked on this frame.

        Args:
            request: HTTP request.
            pk: Frame UUID.

        Returns:
            ``200 OK`` on success.
            ``403 Forbidden`` if the requesting user is not staff.
            ``409 Conflict`` if the frame is not in FAILED state.
        """
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff users can skip frames."},
                status=status.HTTP_403_FORBIDDEN,
            )
        queryset = self.filter_queryset(self.get_queryset())
        frame = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, frame)
        if frame.state != FrameState.FAILED:
            return Response(
                {"detail": f"Only FAILED frames can be skipped (current state: '{frame.state}')."},
                status=status.HTTP_409_CONFLICT,
            )
        frame.state = FrameState.SKIPPED
        frame.save()
        return Response({"status": "skipped"})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def checkpoint(self, request, pk=None, **kwargs):
        """Increment the checkpoint counter for a frame in progress.

        Called by a Worker when it saves a resume checkpoint (e.g. a V-Ray
        ``.vrimg`` file). The frame transitions to ``CHECKPOINT`` state to
        indicate that progress has been persisted.

        Args:
            request: HTTP request.
            pk: Frame UUID.

        Returns:
            ``200 OK`` with the new checkpoint count.
            ``409 Conflict`` if the frame is not in RUNNING state.
        """
        queryset = self.filter_queryset(self.get_queryset())
        frame = get_object_or_404(queryset.select_for_update(), pk=pk)
        self.check_object_permissions(self.request, frame)
        if frame.state not in (FrameState.RUNNING, FrameState.CHECKPOINT):
            return Response(
                {"detail": f"Cannot checkpoint a frame in state '{frame.state}'."},
                status=status.HTTP_409_CONFLICT,
            )

        frame.checkpoint_count += 1
        frame.state = FrameState.CHECKPOINT
        frame.save(update_fields=["checkpoint_count", "state", "updated_at"])
        return Response({"status": "checkpointed", "checkpoint_count": frame.checkpoint_count})
