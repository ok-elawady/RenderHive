from rest_framework import serializers
from .models import WorkerNode

class WorkerNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerNode
        fields = ['id', 'hostname', 'ip_address', 'status', 'system_info', 'last_ping', 'created_at']
        read_only_fields = ['id', 'last_ping', 'created_at']

class WorkerPingSerializer(serializers.Serializer):
    hostname = serializers.CharField(max_length=255)
    ip_address = serializers.IPAddressField(required=False, allow_null=True)
    system_info = serializers.JSONField(required=False, default=dict)
