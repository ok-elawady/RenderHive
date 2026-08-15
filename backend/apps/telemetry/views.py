import datetime
from typing import Any, Dict, List
import uuid

from django.db.models import Avg, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.jobs.models import Task
from apps.jobs.permissions import IsFarmAgent
from apps.workers.models import WorkerNode, WorkerStatus

from .models import DispatchTrace, EventSeverity, FarmEvent, TaskExecutionLog, WorkerMetricSnapshot
from .serializers import (
    ClusterTelemetryHistoryResponseSerializer,
    DispatchTraceSerializer,
    FarmEventSerializer,
    TaskLogDetailSerializer,
    TaskLogIngestSerializer,
    TaskLogListSerializer,
)
from .services import record_event, record_task_log


class TaskLogViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """ViewSet for querying and submitting task execution logs."""

    queryset = TaskExecutionLog.objects.select_related("task", "job").all()
    search_fields = ["worker_hostname", "task__name", "job__name", "error_tail"]
    ordering_fields = ["created_at", "attempt_number", "duration_seconds", "peak_memory_mb"]

    def get_permissions(self):
        if self.action == "create":
            return [IsFarmAgent()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ("retrieve", "latest"):
            return TaskLogDetailSerializer
        if self.action == "create":
            return TaskLogIngestSerializer
        return TaskLogListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        task_pk = self.kwargs.get("task_pk")
        if task_pk:
            qs = qs.filter(task_id=task_pk)
        job_pk = self.kwargs.get("job_pk")
        if job_pk:
            qs = qs.filter(job_id=job_pk)
        return qs

    def create(self, request, task_pk=None):
        """Upload an execution log for a specific task attempt."""
        task = get_object_or_404(Task.objects.select_related("job"), pk=task_pk or request.data.get("task_id"))
        serializer = TaskLogIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        worker_hostname = data.get("worker_hostname") or getattr(task, "worker_name", "") or "unknown"
        log_instance = record_task_log(
            task=task,
            worker_hostname=worker_hostname,
            exit_status=data.get("exit_status", 0),
            log_output=data.get("log_output", ""),
            error_tail=data.get("error_tail", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            peak_memory_mb=data.get("peak_memory_mb", 0),
            output_image_path=data.get("output_image_path", ""),
            attempt_number=data.get("attempt_number"),
        )

        if not log_instance:
            return Response(
                {"detail": "Failed to persist task log."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(TaskLogDetailSerializer(log_instance).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="latest")
    def latest(self, request, task_pk=None):
        """Return the most recent log attempt for a task with full output."""
        task = get_object_or_404(Task, pk=task_pk)
        latest_log = TaskExecutionLog.objects.filter(task=task).order_by("-attempt_number", "-created_at").first()
        if not latest_log:
            return Response(
                {"detail": "No execution logs recorded for this task yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(TaskLogDetailSerializer(latest_log).data)


class DispatchTraceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """ViewSet for inspecting scheduler dispatch evaluations and AI reasoning."""

    queryset = DispatchTrace.objects.select_related("task", "job").all().order_by("-dispatched_at")
    serializer_class = DispatchTraceSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["worker_hostname", "ai_reason", "task__name", "job__name"]
    filterset_fields = ["ai_invoked", "worker_hostname", "job"]

    def get_queryset(self):
        qs = super().get_queryset()
        job_pk = self.kwargs.get("job_pk")
        if job_pk:
            qs = qs.filter(job_id=job_pk)
        limit = self.request.query_params.get("limit")
        if limit and limit.isdigit():
            return qs[: min(int(limit), 200)]
        return qs


class FarmEventViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """ViewSet for querying and recording farm audit and lifecycle events."""

    queryset = FarmEvent.objects.all().order_by("-created_at")
    serializer_class = FarmEventSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["event_type", "message", "actor_username", "target_id"]
    filterset_fields = ["event_type", "severity", "actor_username", "target_type", "target_id"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        """Allows internal farm agents or authenticated users to publish custom operational events."""
        event_type = request.data.get("event_type", "CUSTOM_NOTIFICATION")
        severity = request.data.get("severity", EventSeverity.INFO)
        message = request.data.get("message", "")
        actor_username = request.user.username if request.user.is_authenticated else "SYSTEM"
        target_type = request.data.get("target_type", "")
        target_id = request.data.get("target_id", "")
        payload = request.data.get("payload", {})

        event = record_event(
            event_type=event_type,
            message=message,
            severity=severity,
            actor_username=actor_username,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )
        if not event:
            return Response(
                {"detail": "Failed to record event."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(FarmEventSerializer(event).data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Get cluster telemetry history",
    description="Returns time-bucketed historical hardware metrics (CPU, VRAM, active tasks) across the render farm.",
    parameters=[
        OpenApiParameter(
            name="range",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Time range for aggregation: 1h (default), 24h, or 7d.",
            enum=["1h", "24h", "7d"],
            default="1h",
        ),
        OpenApiParameter(
            name="pool",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Filter metrics to workers in a specific worker pool (UUID or name).",
            required=False,
        ),
        OpenApiParameter(
            name="worker",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Filter metrics to a specific worker hostname.",
            required=False,
        ),
    ],
    responses={200: ClusterTelemetryHistoryResponseSerializer},
)
class ClusterTelemetryHistoryView(generics.GenericAPIView):
    """Returns real historical timeseries metrics for the cluster."""

    permission_classes = [IsAuthenticated]
    serializer_class = ClusterTelemetryHistoryResponseSerializer

    def get(self, request, *args, **kwargs):
        range_param = request.query_params.get("range", "1h").lower()
        pool_param = request.query_params.get("pool")
        worker_param = request.query_params.get("worker")
        now = timezone.now()

        if range_param == "7d":
            start_time = now - datetime.timedelta(days=7)
            points_count = 28  # 6-hour intervals
        elif range_param == "24h":
            start_time = now - datetime.timedelta(hours=24)
            points_count = 24  # 1-hour intervals
        else:  # 1h default
            start_time = now - datetime.timedelta(hours=1)
            points_count = 15  # 4-minute intervals

        interval_seconds = max(1, int((now - start_time).total_seconds() / points_count))
        snapshots = WorkerMetricSnapshot.objects.filter(recorded_at__gte=start_time)

        if worker_param:
            snapshots = snapshots.filter(worker_hostname=worker_param)
        elif pool_param:
            is_valid_uuid = False
            try:
                uuid.UUID(str(pool_param))
                is_valid_uuid = True
            except (ValueError, TypeError):
                is_valid_uuid = False

            pool_filter = (
                (Q(pools__id=pool_param) | Q(pools__name__iexact=pool_param))
                if is_valid_uuid
                else Q(pools__name__iexact=pool_param)
            )
            pool_worker_hostnames = WorkerNode.objects.filter(pool_filter).values_list("hostname", flat=True)
            snapshots = snapshots.filter(worker_hostname__in=pool_worker_hostnames)

        total_snapshots_count = snapshots.count()
        snapshots = snapshots.order_by("recorded_at")
        points: List[Dict[str, Any]] = []

        if snapshots.exists():
            for i in range(points_count):
                bucket_start = start_time + datetime.timedelta(seconds=i * interval_seconds)
                bucket_end = bucket_start + datetime.timedelta(seconds=interval_seconds)
                bucket_qs = snapshots.filter(recorded_at__gte=bucket_start, recorded_at__lt=bucket_end)

                if bucket_qs.exists():
                    agg = bucket_qs.aggregate(
                        avg_cpu=Avg("cpu_percent"),
                        avg_vram=Avg("vram_percent"),
                        avg_mem_used=Avg("memory_used_mb"),
                        avg_mem_total=Avg("memory_total_mb"),
                        active_tasks=Max("active_tasks"),
                        latest_recorded=Max("recorded_at"),
                    )
                    cpu_val = round(agg["avg_cpu"] or 0.0, 1)
                    vram_val = round(agg["avg_vram"] or 0.0, 1)
                    mem_used = agg["avg_mem_used"] or 0.0
                    mem_total = agg["avg_mem_total"] or 0.0
                    ram_val = round((mem_used / mem_total * 100.0), 1) if mem_total > 0 else 0.0
                    active_tasks = int(agg["active_tasks"] or 0)
                    ts = agg["latest_recorded"].isoformat() if agg.get("latest_recorded") else bucket_start.isoformat()
                else:
                    cpu_val = 0.0
                    vram_val = 0.0
                    ram_val = 0.0
                    active_tasks = 0
                    ts = bucket_start.isoformat()

                points.append({
                    "x": round((i / max(1, points_count - 1)) * 100),
                    "cpu": cpu_val,
                    "vram": vram_val,
                    "ram": ram_val,
                    "active_tasks": active_tasks,
                    "timestamp": ts,
                })
        else:
            online_workers_qs = WorkerNode.objects.filter(status__in=[WorkerStatus.ONLINE, WorkerStatus.RENDERING])
            if worker_param:
                online_workers_qs = online_workers_qs.filter(hostname=worker_param)
            elif pool_param:
                is_valid_uuid = False
                try:
                    uuid.UUID(str(pool_param))
                    is_valid_uuid = True
                except (ValueError, TypeError):
                    is_valid_uuid = False

                pool_filter = (
                    (Q(pools__id=pool_param) | Q(pools__name__iexact=pool_param))
                    if is_valid_uuid
                    else Q(pools__name__iexact=pool_param)
                )
                online_workers_qs = online_workers_qs.filter(pool_filter)

            online_workers = list(online_workers_qs)
            cpu_samples = [
                float(w.system_info.get("cpu_percent", 0.0))
                for w in online_workers
                if isinstance(w.system_info, dict) and "cpu_percent" in w.system_info
            ]
            vram_samples = [
                float(w.system_info.get("vram_percent", w.system_info.get("memory_percent", 0.0)))
                for w in online_workers
                if isinstance(w.system_info, dict)
                and ("vram_percent" in w.system_info or "memory_percent" in w.system_info)
            ]
            ram_samples = [
                float(w.system_info.get("memory_percent", 0.0))
                for w in online_workers
                if isinstance(w.system_info, dict) and "memory_percent" in w.system_info
            ]
            current_cpu = round(sum(cpu_samples) / len(cpu_samples), 1) if cpu_samples else 0.0
            current_vram = round(sum(vram_samples) / len(vram_samples), 1) if vram_samples else 0.0
            current_ram = round(sum(ram_samples) / len(ram_samples), 1) if ram_samples else 0.0

            for i in range(points_count):
                bucket_time = start_time + datetime.timedelta(seconds=i * interval_seconds)
                is_latest = i == points_count - 1
                points.append({
                    "x": round((i / max(1, points_count - 1)) * 100),
                    "cpu": current_cpu if is_latest else 0.0,
                    "vram": current_vram if is_latest else 0.0,
                    "ram": current_ram if is_latest else 0.0,
                    "active_tasks": 0,
                    "timestamp": bucket_time.isoformat(),
                })

        latest_point = points[-1] if points else {"cpu": 0.0, "vram": 0.0, "ram": 0.0}
        peak_cpu = round(max((p["cpu"] for p in points), default=0.0), 1)
        peak_vram = round(max((p["vram"] for p in points), default=0.0), 1)
        peak_ram = round(max((p.get("ram", 0.0) for p in points), default=0.0), 1)

        return Response({
            "range": range_param,
            "cpu_load": latest_point["cpu"],
            "vram_usage": latest_point["vram"],
            "ram_usage": latest_point.get("ram", 0.0),
            "peak_cpu": peak_cpu,
            "peak_vram": peak_vram,
            "peak_ram": peak_ram,
            "total_snapshots": total_snapshots_count,
            "points": points,
        })
