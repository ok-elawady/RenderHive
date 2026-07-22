from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.jobs.permissions import IsFarmAgent

from .models import WorkerNode, WorkerPool, WorkerStatus
from .serializers import WorkerNodeSerializer, WorkerPingSerializer, WorkerPoolSerializer


class WorkerPoolViewSet(viewsets.ModelViewSet):
    """
    ViewSet for listing, creating, and managing worker pools.
    """

    queryset = WorkerPool.objects.all()
    serializer_class = WorkerPoolSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "description"]


class WorkerNodeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for listing workers and handling heartbeat pings.
    """

    queryset = WorkerNode.objects.all()
    serializer_class = WorkerNodeSerializer
    search_fields = ["hostname", "ip_address", "status", "tags", "gpu_models"]

    def get_permissions(self):
        if self.action == "ping":
            return [IsFarmAgent()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["post"])
    def ping(self, request):
        """
        Register or update a worker's heartbeat.
        """
        serializer = WorkerPingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        hostname = data["hostname"]

        # Handle pool auto-creation or fetch
        pool_names = data.get("pool_names", [])
        pool_instances = []
        for p_name in pool_names:
            if p_name:
                p_instance, _ = WorkerPool.objects.get_or_create(name=p_name)
                pool_instances.append(p_instance)

        worker, created = WorkerNode.objects.update_or_create(
            hostname=hostname,
            defaults={
                "ip_address": data.get("ip_address"),
                "system_info": data.get("system_info", {}),
                "tags": data.get("tags", []),
                "cores": data.get("cores", 1),
                "memory_mb": data.get("memory_mb", 4096),
                "gpu_models": data.get("gpu_models", []),
                "last_ping": timezone.now(),
            },
        )

        # Set ManyToMany pools
        if pool_instances:
            worker.pools.set(pool_instances)

        # Only set to ONLINE if it was offline. If it's RENDERING, keep it RENDERING.
        if worker.status == WorkerStatus.OFFLINE:
            worker.status = WorkerStatus.ONLINE
            worker.save(update_fields=["status"])

        # Opportunistic cleanup of offline workers
        threshold = timezone.now() - timezone.timedelta(seconds=30)
        WorkerNode.objects.filter(last_ping__lt=threshold).exclude(status=WorkerStatus.OFFLINE).update(
            status=WorkerStatus.OFFLINE
        )

        return Response({"status": "ok", "worker_status": worker.status})
