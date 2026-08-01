from rest_framework import serializers

from .models import WorkerNode, WorkerPool, WorkerStatus


class WorkerNodeSummarySerializer(serializers.ModelSerializer):
    """Compact worker representation used inside pool detail responses."""

    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = WorkerNode
        fields = [
            "id",
            "hostname",
            "ip_address",
            "status",
            "tags",
            "cores",
            "memory_mb",
            "gpu_models",
            "capabilities",
            "system_info",
            "last_ping",
        ]
        read_only_fields = fields

    def get_capabilities(self, obj):
        system_info = obj.system_info if isinstance(obj.system_info, dict) else {}
        capabilities = system_info.get("capabilities")
        return capabilities if isinstance(capabilities, dict) else {}


class WorkerPoolSerializer(serializers.ModelSerializer):
    worker_count = serializers.IntegerField(read_only=True, default=0)
    online_worker_count = serializers.IntegerField(read_only=True, default=0)
    rendering_worker_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = WorkerPool
        fields = [
            "id",
            "name",
            "description",
            "worker_count",
            "online_worker_count",
            "rendering_worker_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "worker_count",
            "online_worker_count",
            "rendering_worker_count",
            "created_at",
            "updated_at",
        ]


class WorkerPoolDetailSerializer(WorkerPoolSerializer):
    workers = WorkerNodeSummarySerializer(many=True, read_only=True)

    class Meta(WorkerPoolSerializer.Meta):
        fields = WorkerPoolSerializer.Meta.fields + ["workers"]
        read_only_fields = WorkerPoolSerializer.Meta.read_only_fields + ["workers"]


class WorkerNodeSerializer(serializers.ModelSerializer):
    pools = WorkerPoolSerializer(many=True, read_only=True)
    capabilities = serializers.SerializerMethodField()

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
            "capabilities",
            "system_info",
            "last_ping",
            "created_at",
        ]
        read_only_fields = ["id", "capabilities", "last_ping", "created_at"]

    def get_capabilities(self, obj):
        system_info = obj.system_info if isinstance(obj.system_info, dict) else {}
        capabilities = system_info.get("capabilities")
        return capabilities if isinstance(capabilities, dict) else {}


class WorkerPingSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=255)
    ip_address = serializers.IPAddressField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=WorkerStatus.choices, required=False)
    system_info = serializers.JSONField(required=False, default=dict)
    capabilities = serializers.JSONField(required=False)

    # Capability fields retained for legacy and current workers.
    pool_names = serializers.ListField(
        child=serializers.CharField(max_length=128),
        required=False,
        default=list,
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
    )
    cores = serializers.IntegerField(min_value=1, required=False, default=1)
    memory_mb = serializers.IntegerField(min_value=1, required=False, default=4096)
    gpu_models = serializers.ListField(
        child=serializers.CharField(max_length=128),
        required=False,
        default=list,
    )

    def validate(self, attrs):
        system_info = attrs.get("system_info")
        if not isinstance(system_info, dict):
            system_info = {}

        capabilities = attrs.get("capabilities")
        if isinstance(capabilities, dict):
            system_info = dict(system_info)
            system_info["capabilities"] = capabilities
        attrs["system_info"] = system_info
        return attrs
