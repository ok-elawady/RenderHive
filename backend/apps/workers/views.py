from django.utils import timezone
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import WorkerNode, WorkerStatus
from .serializers import WorkerNodeSerializer, WorkerPingSerializer
from apps.jobs.permissions import IsFarmAgent

class WorkerNodeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for listing workers and handling heartbeat pings.
    """
    queryset = WorkerNode.objects.all()
    serializer_class = WorkerNodeSerializer
    
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
        
        worker, created = WorkerNode.objects.update_or_create(
            hostname=hostname,
            defaults={
                "ip_address": data.get("ip_address"),
                "system_info": data.get("system_info", {}),
                "last_ping": timezone.now(),
            }
        )
        
        # Only set to ONLINE if it was offline. If it's RENDERING, keep it RENDERING.
        if worker.status == WorkerStatus.OFFLINE:
            worker.status = WorkerStatus.ONLINE
            worker.save(update_fields=["status"])
            
        # Opportunistic cleanup of offline workers
        threshold = timezone.now() - timezone.timedelta(seconds=30)
        WorkerNode.objects.filter(last_ping__lt=threshold).exclude(status=WorkerStatus.OFFLINE).update(status=WorkerStatus.OFFLINE)
            
        return Response({"status": "ok", "worker_status": worker.status})
