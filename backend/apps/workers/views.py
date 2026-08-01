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

        threshold = timezone.now() - timezone.timedelta(seconds=30)
        WorkerNode.objects.filter(last_ping__lt=threshold).exclude(
            status=WorkerStatus.OFFLINE
        ).update(status=WorkerStatus.OFFLINE)

        system_info = worker.system_info if isinstance(worker.system_info, dict) else {}
        capabilities = system_info.get("capabilities")
        if not isinstance(capabilities, dict):
            capabilities = {}

        return Response(
            {
                "status": "ok",
                "worker_id": worker.pk,
                "worker_status": worker.status,
                "capabilities": capabilities,
            }
        )
