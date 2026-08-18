from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.jobs.permissions import IsFarmAgent

from .models import WorkerNode, WorkerPool, WorkerStatus
from .serializers import (
    WorkerNodeSerializer,
    WorkerNodeSummarySerializer,
    WorkerPingSerializer,
    WorkerPoolDetailSerializer,
    WorkerPoolSerializer,
)


class WorkerPoolViewSet(viewsets.ModelViewSet):
    """ViewSet for listing, creating, and managing worker pools."""

    permission_classes = [IsAuthenticated]
    search_fields = ["name", "description"]

    def get_queryset(self):
        queryset = WorkerPool.objects.annotate(
            worker_count=Count("workers", distinct=True),
            online_worker_count=Count(
                "workers",
                filter=Q(workers__status=WorkerStatus.ONLINE),
                distinct=True,
            ),
            rendering_worker_count=Count(
                "workers",
                filter=Q(workers__status=WorkerStatus.RENDERING),
                distinct=True,
            ),
        ).order_by("name")
        if self.action in ("retrieve", "workers"):
            queryset = queryset.prefetch_related("workers")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WorkerPoolDetailSerializer
        return WorkerPoolSerializer

    @action(detail=True, methods=["get"])
    def workers(self, request, pk=None):
        """Return workers assigned to this pool.

        This explicit endpoint is convenient for DCC submitters while the normal
        pool detail endpoint also embeds the same worker list.
        """

        pool = self.get_object()
        queryset = pool.workers.all().order_by("-last_ping")
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = WorkerNodeSummarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(WorkerNodeSummarySerializer(queryset, many=True).data)


class WorkerNodeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """ViewSet for listing workers and handling heartbeat pings."""

    serializer_class = WorkerNodeSerializer
    search_fields = ["hostname", "ip_address", "status", "tags", "gpu_models"]

    def get_queryset(self):
        return WorkerNode.objects.prefetch_related("pools").all()

    def get_permissions(self):
        if self.action == "ping":
            return [IsFarmAgent()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["post"])
    def ping(self, request):
        """Register or update a worker heartbeat and its DCC capabilities."""

        serializer = WorkerPingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        hostname = data["hostname"]

        pool_names = data.get("pool_names", [])
        pool_instances = []
        for pool_name in pool_names:
            clean_name = str(pool_name or "").strip()
            if clean_name:
                pool, _ = WorkerPool.objects.get_or_create(name=clean_name)
                pool_instances.append(pool)

        worker, _created = WorkerNode.objects.update_or_create(
            hostname=hostname,
            defaults={
                "ip_address": data.get("ip_address"),
                "system_info": data.get("system_info", {}),
                "tags": list(dict.fromkeys(data.get("tags", []))),
                "cores": data.get("cores", 1),
                "memory_mb": data.get("memory_mb", 4096),
                "gpu_models": list(dict.fromkeys(data.get("gpu_models", []))),
                "last_ping": timezone.now(),
            },
        )

        # An explicitly supplied empty list means "remove all pool memberships".
        # Omitting pool_names preserves assignments managed from the web UI.
        if "pool_names" in request.data:
            worker.pools.set(pool_instances)

        requested_status = data.get("status")
        if requested_status in WorkerStatus.values:
            next_status = requested_status
        elif worker.status == WorkerStatus.OFFLINE:
            next_status = WorkerStatus.ONLINE
        else:
            # Legacy workers do not report status. Preserve RENDERING until they
            # explicitly report ONLINE or become stale.
            next_status = worker.status

        if worker.status != next_status:
            worker.status = next_status
            worker.save(update_fields=["status"])

        stale_threshold_secs = getattr(settings, "WORKER_STALE_THRESHOLD_SECONDS", 30)
        threshold = timezone.now() - timezone.timedelta(seconds=stale_threshold_secs)
        WorkerNode.objects.filter(last_ping__lt=threshold).exclude(
            status=WorkerStatus.OFFLINE
        ).update(status=WorkerStatus.OFFLINE)

        system_info = worker.system_info if isinstance(worker.system_info, dict) else {}
        capabilities = system_info.get("capabilities")
        if not isinstance(capabilities, dict):
            capabilities = {}

        # Telemetry: Record historical hardware metric snapshot
        from apps.telemetry.services import record_worker_metrics

        cpu_val = float(system_info.get("cpu_percent", 0.0))
        mem_used = int(system_info.get("used_memory_mb", system_info.get("memory_used_mb", 0)))
        mem_total = int(data.get("memory_mb", system_info.get("total_memory_mb", 4096)))

        if "vram_percent" in system_info:
            vram_val = float(system_info["vram_percent"])
        elif float(system_info.get("gpu_vram_mb", 0)) > 0:
            vram_used = float(system_info.get("gpu_vram_used_mb", 0))
            vram_total = float(system_info.get("gpu_vram_mb", 1))
            vram_val = round((vram_used / vram_total) * 100.0, 1)
        else:
            vram_val = 0.0

        active_count = 1 if worker.status == WorkerStatus.RENDERING else 0

        record_worker_metrics(
            worker_hostname=hostname,
            cpu_percent=cpu_val,
            memory_used_mb=mem_used,
            memory_total_mb=mem_total,
            vram_percent=vram_val,
            active_tasks=active_count,
        )

        return Response(
            {
                "status": "ok",
                "worker_id": worker.pk,
                "worker_status": worker.status,
                "capabilities": capabilities,
            }
        )

