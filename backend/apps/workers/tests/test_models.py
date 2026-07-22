import pytest

from apps.workers.models import WorkerNode, WorkerPool, WorkerStatus

pytestmark = pytest.mark.django_db


class TestWorkerPoolModel:
    def test_worker_pool_creation(self):
        pool = WorkerPool.objects.create(name="high-priority", description="For urgent jobs")
        assert pool.name == "high-priority"
        assert pool.description == "For urgent jobs"
        assert str(pool) == "high-priority"


class TestWorkerNodeModel:
    def test_worker_node_creation(self):
        worker = WorkerNode.objects.create(
            hostname="render-node-01",
            ip_address="192.168.1.100",
            cores=32,
            memory_mb=65536,
            tags=["cpu", "fast"],
            gpu_models=["RTX 4090"],
        )
        assert worker.hostname == "render-node-01"
        assert worker.status == WorkerStatus.OFFLINE
        assert worker.cores == 32
        assert worker.memory_mb == 65536
        assert worker.tags == ["cpu", "fast"]
        assert worker.gpu_models == ["RTX 4090"]
        assert str(worker) == "render-node-01"

    def test_worker_node_pools_relationship(self):
        worker = WorkerNode.objects.create(hostname="node-with-pools")
        pool1 = WorkerPool.objects.create(name="pool1")
        pool2 = WorkerPool.objects.create(name="pool2")

        worker.pools.add(pool1, pool2)
        assert worker.pools.count() == 2
        assert list(worker.pools.values_list("name", flat=True).order_by("name")) == ["pool1", "pool2"]
