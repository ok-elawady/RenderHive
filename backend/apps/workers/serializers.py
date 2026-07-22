from rest_framework import serializers

from .models import WorkerNode, WorkerPool


class WorkerPoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerPool
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class WorkerNodeSerializer(serializers.ModelSerializer):
    pools = WorkerPoolSerializer(many=True, read_only=True)

    class Meta:
        model = WorkerNode
        fields = [
            "id",
            "hostname",
            "ip_address",
            "status",
            "pools",
            "tags",
            "cores",
            "memory_mb",
            "gpu_models",
            "system_info",
            "last_ping",
            "created_at",
        ]
        read_only_fields = ["id", "last_ping", "created_at"]


class WorkerPingSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=255)
    ip_address = serializers.IPAddressField(required=False, allow_null=True)
    system_info = serializers.JSONField(required=False, default=dict)

    # Capability fields
    pool_names = serializers.ListField(child=serializers.CharField(max_length=128), required=False, default=list)
    tags = serializers.ListField(child=serializers.CharField(max_length=64), required=False, default=list)
    cores = serializers.IntegerField(min_value=1, required=False, default=1)
    memory_mb = serializers.IntegerField(min_value=1, required=False, default=4096)
    gpu_models = serializers.ListField(child=serializers.CharField(max_length=128), required=False, default=list)
