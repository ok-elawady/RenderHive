import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.workers.models import WorkerNode, WorkerPool, WorkerStatus

User = get_user_model()
pytestmark = pytest.mark.django_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def farm_agent_user(db):
    """A farm_service user in the farm_agents group (Worker / DCC plugin)."""
    group, _ = Group.objects.get_or_create(name="farm_agents")
    agent = User.objects.create_user(username="farm_service", password="!")
    agent.groups.add(group)
    return agent


@pytest.fixture
def regular_user(db):
    """A standard authenticated human user."""
    return User.objects.create_user(username="artist", password="pass")


@pytest.fixture
def farm_client(farm_agent_user):
    """API client authenticated as the farm_service agent."""
    client = APIClient()
    token = Token.objects.create(user=farm_agent_user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def user_client(regular_user):
    """API client authenticated as a regular user."""
    client = APIClient()
    token = Token.objects.create(user=regular_user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def anon_client():
    """Unauthenticated API client."""
    return APIClient()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestWorkerPingAPI:
    """Tests for the /api/workers/ping/ endpoint."""
    
    def test_ping_requires_farm_agent(self, user_client, anon_client):
        """Only users in the farm_agents group can ping."""
        payload = {"hostname": "node-01"}
        
        # Anon should fail
        res = anon_client.post("/api/workers/ping/", payload, format="json")
        assert res.status_code == 403
        
        # Regular user should fail
        res = user_client.post("/api/workers/ping/", payload, format="json")
        assert res.status_code == 403

    def test_ping_creates_new_worker(self, farm_client):
        """A ping from a new hostname creates a WorkerNode."""
        payload = {
            "hostname": "new-node",
            "ip_address": "10.0.0.5",
            "system_info": {"cpu_percent": 45},
            "pool_names": ["render-farm", "gpu-nodes"],
            "tags": ["fast", "linux"],
            "cores": 64,
            "memory_mb": 128000,
            "gpu_models": ["RTX 4090"]
        }
        res = farm_client.post("/api/workers/ping/", payload, format="json")
        
        assert res.status_code == 200
        assert res.data["status"] == "ok"
        assert res.data["worker_status"] == WorkerStatus.ONLINE
        
        worker = WorkerNode.objects.get(hostname="new-node")
        assert worker.ip_address == "10.0.0.5"
        assert worker.status == WorkerStatus.ONLINE
        assert worker.system_info["cpu_percent"] == 45
        assert worker.tags == ["fast", "linux"]
        assert worker.cores == 64
        assert worker.memory_mb == 128000
        assert worker.gpu_models == ["RTX 4090"]
        assert list(worker.pools.values_list("name", flat=True).order_by("name")) == ["gpu-nodes", "render-farm"]

    def test_ping_updates_existing_worker(self, farm_client):
        """A ping from an existing hostname updates last_ping and system_info."""
        worker = WorkerNode.objects.create(
            hostname="existing-node",
            ip_address="10.0.0.6",
            status=WorkerStatus.OFFLINE,
            last_ping=timezone.now() - timezone.timedelta(minutes=5)
        )
        old_ping = worker.last_ping
        
        payload = {
            "hostname": "existing-node",
            "system_info": {"memory_percent": 80}
        }
        res = farm_client.post("/api/workers/ping/", payload, format="json")
        
        assert res.status_code == 200
        assert res.data["worker_status"] == WorkerStatus.ONLINE
        
        worker.refresh_from_db()
        assert worker.status == WorkerStatus.ONLINE
        assert worker.system_info["memory_percent"] == 80
        assert worker.last_ping > old_ping

    def test_ping_preserves_rendering_status(self, farm_client):
        """If a worker is RENDERING, pinging should not change it back to ONLINE."""
        worker = WorkerNode.objects.create(
            hostname="busy-node",
            status=WorkerStatus.RENDERING
        )
        
        payload = {"hostname": "busy-node"}
        res = farm_client.post("/api/workers/ping/", payload, format="json")
        
        assert res.status_code == 200
        assert res.data["worker_status"] == WorkerStatus.RENDERING
        
        worker.refresh_from_db()
        assert worker.status == WorkerStatus.RENDERING


    def test_ping_cleans_up_stale_workers(self, farm_client):
        """Pinging opportunistically marks stale workers as OFFLINE."""
        stale_worker = WorkerNode.objects.create(
            hostname="stale-node",
            status=WorkerStatus.ONLINE,
            last_ping=timezone.now() - timezone.timedelta(seconds=45)
        )
        
        payload = {"hostname": "active-node"}
        res = farm_client.post("/api/workers/ping/", payload, format="json")
        assert res.status_code == 200
        
        stale_worker.refresh_from_db()
        assert stale_worker.status == WorkerStatus.OFFLINE


class TestWorkerListAPI:
    """Tests for the /api/workers/ read-only endpoints."""

    def test_list_workers(self, user_client, farm_client):
        """Authenticated users can list workers."""
        WorkerNode.objects.create(hostname="node-a")
        WorkerNode.objects.create(hostname="node-b")
        
        res = user_client.get("/api/workers/")
        assert res.status_code == 200
        assert len(res.data["results"]) == 2
        
        res2 = farm_client.get("/api/workers/")
        assert res2.status_code == 200

    def test_list_workers_requires_auth(self, anon_client):
        """Anonymous users cannot list workers."""
        res = anon_client.get("/api/workers/")
        assert res.status_code == 403


class TestWorkerPoolAPI:
    """Tests for the /api/pools/ endpoints."""

    def test_list_pools(self, user_client):
        WorkerPool.objects.create(name="pool1", description="desc1")
        WorkerPool.objects.create(name="pool2")
        
        res = user_client.get("/api/pools/")
        assert res.status_code == 200
        assert len(res.data["results"]) == 2
        assert res.data["results"][0]["name"] == "pool1"
        
    def test_create_pool(self, user_client):
        payload = {"name": "new-pool", "description": "Brand new"}
        res = user_client.post("/api/pools/", payload, format="json")
        
        assert res.status_code == 201
        assert WorkerPool.objects.filter(name="new-pool").exists()
        
    def test_pools_require_auth(self, anon_client):
        res = anon_client.get("/api/pools/")
        assert res.status_code == 403
