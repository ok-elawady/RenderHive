import pytest
from apps.workers.models import WorkerNode, WorkerStatus

pytestmark = pytest.mark.django_db


class TestWorkerNodeModel:
    def test_worker_node_creation(self):
        worker = WorkerNode.objects.create(hostname="render-node-01", ip_address="192.168.1.100")
        assert worker.hostname == "render-node-01"
        assert worker.status == WorkerStatus.OFFLINE
        assert str(worker) == "render-node-01"
