# Complete Setup & Running Guide

## System Requirements

### Minimum Hardware

- **CPU**: 4+ cores (for orchestration)
- **RAM**: 16 GB (8 GB for services + 8 GB for headroom)
- **Disk**: 50 GB (database + logs + temporary renders)
- **GPU**: Optional (for AI scheduler acceleration)

### Supported Operating Systems

- **Development**: macOS 12+, Ubuntu 20.04+, Windows 11 Pro/Enterprise (WSL2)
- **Production**: Ubuntu 22.04+, Rocky Linux 8+, Debian 12+

### Software Prerequisites

- **Docker & Docker Compose** v2.15+
- **Python** 3.13+ (if running native development)
- **Node.js** 20+ (for frontend development)
- **Git** 2.30+
- **PostgreSQL** 16 client tools (for troubleshooting)

---

## Architecture Overview for Deployment

RenderHive consists of several interconnected services:

```
Services (Docker Compose):
  postgres:16        (database)
  redis:7            (cache + message broker)
  api:8000           (Django REST API)
  celery-worker      (task dispatcher)
  celery-beat        (scheduler)
  ai-scheduler:8001  (LLM service, optional)
  frontend:3000      (Next.js dashboard)
  nginx              (reverse proxy)

External:
  Worker nodes       (render machines, connect via HTTP)
  Maya (plugin)      (artist workstations)
```

All services are defined in `docker-compose.yml`.

---

## Part A: Local Development Setup

### Step 1: Clone Repository

```bash
cd /path/to/workspace
git clone https://github.com/your-org/renderhive.git
cd RenderHive
```

### Step 2: Environment Configuration

Create `.env` file in repository root:

```bash
# BACKEND CONFIGURATION
SECRET_KEY=your-super-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,api,renderhive.local

# DATABASE
POSTGRES_DB=renderhive
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgres://postgres:postgres@postgres:5432/renderhive

# CACHE & MESSAGE BROKER
REDIS_URL=redis://redis:6379/1

# AUTHENTICATION
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://renderhive.local
CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://renderhive.local

# DJANGO SUPERUSER (auto-created on first run)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@renderhive.local
DJANGO_SUPERUSER_PASSWORD=admin

# AI SCHEDULER
AI_SCHEDULER_URL=http://ai_scheduler:8001
AI_SCHEDULER_ENABLED=False  # Set True to enable

# FRONTEND
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Step 3: Start Services with Docker Compose

```bash
# Build and start all services in background
docker-compose up -d

# Monitor logs
docker-compose logs -f

# Specific service logs
docker-compose logs -f api        # Django API
docker-compose logs -f celery-worker  # Task dispatcher
docker-compose logs -f frontend   # Next.js app
```

**First Run Initialization** (automatic):

1. PostgreSQL container starts, creates `renderhive` database
2. Django migrations run: `manage.py migrate`
3. Django superuser created: `admin` / `admin`
4. Static files collected: `manage.py collectstatic`
5. Redis initializes
6. Celery workers connect to broker
7. Frontend builds Next.js app

### Step 4: Verify Services Running

```bash
# Check all containers are healthy
docker-compose ps

# Expected output:
# NAME                   IMAGE                 STATUS
# renderhive-api-1       renderhive_api:latest   Up (healthy)
# renderhive-postgres-1  postgres:16-alpine      Up (healthy)
# renderhive-redis-1     redis:7-alpine          Up
# renderhive-frontend-1  renderhive_frontend:latest   Up
# renderhive-celery-worker-1   renderhive_api:latest   Up
# renderhive-celery-beat-1     renderhive_api:latest   Up
```

### Step 5: Access Services

| Service             | URL                                       | Credentials         |
| ------------------- | ----------------------------------------- | ------------------- |
| **Dashboard**       | http://localhost:3000                     | —                   |
| **API**             | http://localhost:8000                     | —                   |
| **OpenAPI Docs**    | http://localhost:8000/api/schema/swagger/ | —                   |
| **Django Admin**    | http://localhost:8000/admin               | admin / admin       |
| **Redis Commander** | http://localhost:8081 (if added)          | —                   |
| **PostgreSQL**      | localhost:5432                            | postgres / postgres |

### Step 6: Create First Worker Pool

```bash
# Access Django shell
docker-compose exec api python manage.py shell

# Create pool
>>> from apps.workers.models import WorkerPool
>>> pool = WorkerPool.objects.create(
...     name="STUDIO_A",
...     description="Main rendering pool"
... )
>>> pool.save()
>>> exit()
```

---

## Part B: Native Development Setup (Without Docker)

### For Frontend Development

```bash
cd frontend

# Install dependencies
pnpm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_WS_URL=ws://localhost:8000" >> .env.local

# Start dev server (with hot reload)
pnpm dev

# App available at http://localhost:3000
```

### For Backend Development

**Prerequisites**: Python 3.13+, PostgreSQL running

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate venv
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -e ".[dev]"

# Create .env in backend/
echo "PYTHONUNBUFFERED=1" > .env
echo "SECRET_KEY=dev-secret-key" >> .env
echo "DEBUG=True" >> .env
echo "DATABASE_URL=postgres://postgres:postgres@localhost:5432/renderhive" >> .env
echo "REDIS_URL=redis://localhost:6379/1" >> .env

# Create database (if using external PostgreSQL)
psql -h localhost -U postgres -c "CREATE DATABASE renderhive;"

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start Django dev server
python manage.py runserver 0.0.0.0:8000

# In another terminal, start Celery worker
celery -A config worker -l info

# In another terminal, start Celery Beat
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**API available at**: http://localhost:8000

---

## Part C: Running Your First Job

### Step 1: Log In

```bash
# Web browser
open http://localhost:3000

# Or use credentials
Username: admin
Password: admin
```

### Step 2: Register a Worker (Development Mode)

**Option A: Simulate a Worker via CLI**

```bash
# In backend container or native python env
cd backend

# Create a test worker
python manage.py shell

>>> from apps.workers.models import Worker, WorkerPool
>>> pool = WorkerPool.objects.first()
>>> worker = Worker.objects.create(
...     name="test-worker-1",
...     pool=pool,
...     state="ONLINE",
...     capabilities={
...         "cpu_cores": 8,
...         "memory_gb": 16,
...         "gpu_count": 1,
...         "gpu_memory_gb": [8.0],
...         "software": ["maya2024", "arnold7"]
...     }
... )
>>> worker.save()
>>> exit()
```

**Option B: Run Real Worker Application** (see Part D)

### Step 3: Submit a Test Job via API

```bash
# Submit job with curl
curl -X POST http://localhost:8000/api/jobs/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -d '{
    "name": "test_job_001",
    "visible_name": "Test Job",
    "project": "TestProject",
    "priority": 50,
    "log_directory": "/tmp/renderhive/logs",
    "layers": [
      {
        "name": "beauty",
        "type": "RENDER",
        "order": 1,
        "tasks": [
          {"frame_start": 1, "frame_end": 10, "max_retries": 3},
          {"frame_start": 11, "frame_end": 20, "max_retries": 3}
        ]
      }
    ]
  }'

# Copy the returned job_id
# Example response:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "name": "test_job_001",
#   "state": "PENDING"
# }
```

### Step 4: Monitor in Dashboard

```bash
# Open dashboard
open http://localhost:3000/jobs

# You should see:
# - "test_job_001" in the queue
# - State: PENDING → RUNNING
# - Task breakdown showing 2 tasks
```

### Step 5: Simulate Task Execution

```bash
# Manually mark a task as completed
python manage.py shell

>>> from apps.jobs.models import Task
>>> task = Task.objects.first()
>>> task.state = "SUCCEEDED"
>>> task.exit_code = 0
>>> task.save()
>>> exit()

# Dashboard updates automatically (via WebSocket)
# Task marked as SUCCEEDED
# Job progress increases
```

---

## Part D: Deploy Worker Application

### On Windows Render Node

#### 1. Install Python 3.11+

```powershell
# Download from python.org or use Chocolatey
choco install python311
```

#### 2. Clone Repository on Worker

```powershell
git clone https://github.com/your-org/renderhive.git C:\RenderHive
cd C:\RenderHive\worker
```

#### 3. Create Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### 4. Configuration

Create `%APPDATA%\RenderHive\config.json`:

```json
{
  "api_url": "http://server.renderhive.local:8000",
  "api_token": "sk_live_YOUR_WORKER_TOKEN",
  "worker_id": "render-node-01",
  "pool": "STUDIO_A",
  "max_concurrent_tasks": 2,
  "dcc_paths": {
    "maya": "C:\\Program Files\\Autodesk\\Maya2024\\bin\\render.exe",
    "houdini": "C:\\Program Files\\Side Effects\\Houdini20\\bin\\hrender.exe",
    "blender": "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe"
  },
  "telemetry_interval_sec": 5,
  "heartbeat_interval_sec": 5
}
```

#### 5. Run Worker

```powershell
python app.py

# PySide6 UI should launch
# Monitor → Status should show "CONNECTED"
```

#### 6. Register Worker in Dashboard

```
Admin → Workers → Register New Worker
Name: render-node-01
Pool: STUDIO_A
```

---

## Part E: Deploy in Production

### Prerequisites

- Kubernetes cluster (EKS, AKS, GKE, or self-hosted)
- Container registry (Docker Hub, ECR, ACR, Artifactory)
- PostgreSQL 16+ managed database
- Redis 7+ managed cache
- Load balancer or ingress controller

### Multi-Node Architecture

```
Load Balancer (SSL termination)
    ↓
Nginx Ingress
    ├─ /api → Django API pods (3+)
    ├─ /dashboard → Frontend pods (2+)
    └─ /ws → WebSocket pods (2+, sticky sessions)

Stateful Services:
    ├─ PostgreSQL (managed, multi-AZ backup)
    ├─ Redis Cluster (managed, HA)
    └─ MinIO S3 (persistent storage for logs/renders)

Background Tasks:
    ├─ Celery Worker Deployment (HPA, min 2)
    ├─ Celery Beat Deployment (1)
    └─ AI Scheduler Deployment (optional, 1-2)

Monitoring:
    ├─ Prometheus (metrics)
    ├─ ELK Stack (logs)
    └─ Jaeger (tracing)
```

### Deployment Steps

**1. Prepare Container Images**

```bash
# Build and push images
docker build -t myregistry.azurecr.io/renderhive-api:v0.2.0 backend/
docker build -t myregistry.azurecr.io/renderhive-frontend:v0.2.0 frontend/
docker push myregistry.azurecr.io/renderhive-api:v0.2.0
docker push myregistry.azurecr.io/renderhive-frontend:v0.2.0
```

**2. Create Kubernetes Manifests** (example for AKS):

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: renderhive

---
# k8s/django-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: renderhive
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: myregistry.azurecr.io/renderhive-api:v0.2.0
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: renderhive-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: renderhive-secrets
                  key: redis-url
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 1000m
              memory: 2Gi
          livenessProbe:
            httpGet:
              path: /health/
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10

---
# k8s/celery-worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
  namespace: renderhive
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
  selector:
    matchLabels:
      app: celery-worker
  template:
    metadata:
      labels:
        app: celery-worker
    spec:
      containers:
        - name: celery
          image: myregistry.azurecr.io/renderhive-api:v0.2.0
          command:
            - celery
            - -A
            - config
            - worker
            - -l
            - info
            - -c
            - "4"
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: renderhive-secrets
                  key: database-url
          resources:
            requests:
              cpu: 1000m
              memory: 2Gi
            limits:
              cpu: 2000m
              memory: 4Gi
```

**3. Deploy to Kubernetes**

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml  # Store DB/Redis URLs
kubectl apply -f k8s/django-deployment.yaml
kubectl apply -f k8s/celery-worker-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/ingress.yaml
```

**4. Verify Deployment**

```bash
kubectl get pods -n renderhive
kubectl logs -f deploy/api -n renderhive
kubectl describe svc api -n renderhive
```

---

## Part F: Configuration Reference

### Django Environment Variables

| Variable                     | Default                    | Description                       |
| ---------------------------- | -------------------------- | --------------------------------- |
| `DEBUG`                      | `False`                    | Enable Django debug mode          |
| `SECRET_KEY`                 | (required)                 | Django secret key (min 50 chars)  |
| `ALLOWED_HOSTS`              | `localhost,127.0.0.1`      | Comma-separated allowed hostnames |
| `DATABASE_URL`               | —                          | PostgreSQL connection string      |
| `REDIS_URL`                  | `redis://localhost:6379/1` | Redis connection string           |
| `CORS_ALLOWED_ORIGINS`       | —                          | Frontend URL for CORS             |
| `AI_SCHEDULER_URL`           | `http://localhost:8001`    | AI service endpoint               |
| `AI_SCHEDULER_ENABLED`       | `False`                    | Enable AI tie-breaker             |
| `CELERY_WORKER_PREFETCH`     | `4`                        | Tasks prefetched per worker       |
| `TASK_DISPATCH_INTERVAL_SEC` | `1`                        | Seconds between dispatch cycles   |

### Frontend Environment Variables

| Variable                          | Default                 | Description            |
| --------------------------------- | ----------------------- | ---------------------- |
| `NEXT_PUBLIC_API_URL`             | `http://localhost:8000` | Backend API URL        |
| `NEXT_PUBLIC_WS_URL`              | `ws://localhost:8000`   | WebSocket URL          |
| `NEXT_PUBLIC_LOG_LEVEL`           | `info`                  | Console log level      |
| `NEXT_PUBLIC_POLLING_INTERVAL_MS` | `5000`                  | Fallback poll interval |

### Worker Application Configuration

See [Part D: Deploy Worker Application](#part-d-deploy-worker-application) for `config.json` schema.

---

## Part G: Troubleshooting

### Services Won't Start

**Symptom**: `docker-compose up` fails with network errors

**Solution**:

```bash
# Check Docker daemon
docker ps

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check service logs
docker-compose logs api
```

### Database Migrations Failed

**Symptom**: API container exits with "no such table"

**Solution**:

```bash
# Manually run migrations
docker-compose exec api python manage.py migrate

# Or in native setup
python manage.py migrate

# Check migration status
python manage.py showmigrations
```

### Worker Can't Connect to API

**Symptom**: Worker shows "DISCONNECTED" status

**Solution**:

```bash
# Verify API is accessible
curl http://localhost:8000/health/

# Check network connectivity
ping server.renderhive.local

# Verify API token is valid
curl -H "Authorization: Bearer sk_live_YOUR_TOKEN" \
  http://localhost:8000/api/workers/me/
```

### Tasks Not Dispatching

**Symptom**: Tasks stay in READY state indefinitely

**Solution**:

```bash
# Check Celery worker is running
docker-compose ps celery-worker

# Check Celery logs
docker-compose logs -f celery-worker

# Verify Redis connectivity
docker-compose exec redis redis-cli ping
# Should return: PONG

# Check task queue depth
python manage.py shell
>>> from celery.app.control import Inspect
>>> i = Inspect()
>>> i.active()  # Active tasks
>>> i.scheduled()  # Scheduled tasks
```

### High Memory Usage

**Symptom**: Docker container using >50% of system memory

**Solution**:

```bash
# Check memory per container
docker stats

# Limit container memory
docker-compose down
# Edit docker-compose.yml, add under service:
#   deploy:
#     resources:
#       limits:
#         memory: 2G

# Tune database connection pool
# In settings/base.py:
DATABASES['default']['CONN_MAX_AGE'] = 300  # 5-min connection reuse
```

---

## Part H: Monitoring & Health Checks

### Health Endpoints

```bash
# API health
curl http://localhost:8000/health/

# Database connectivity
curl http://localhost:8000/api/health/db/

# Redis connectivity
curl http://localhost:8000/api/health/cache/

# Celery worker status
curl http://localhost:8000/api/health/celery/
```

### Metrics Collection (Prometheus-compatible)

```bash
# Export metrics
curl http://localhost:8000/metrics/

# Format: Prometheus text format
# Example:
# django_http_requests_before_middleware_total{method="GET",status="200"} 1234.0
# django_request_latency_seconds_bucket{method="GET"} 0.025
```

### Logging

**Log Locations** (in Docker):

- API: `docker-compose logs api`
- Celery: `docker-compose logs celery-worker`
- Frontend: `docker-compose logs frontend`

**Log Levels**:

```python
# In Django settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': '/var/log/renderhive/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

---

## Part I: Security Checklist

### Before Production Deployment

- [ ] Change `SECRET_KEY` to a unique, cryptographically random string (50+ characters)
- [ ] Set `DEBUG=False`
- [ ] Update `ALLOWED_HOSTS` to production domain(s)
- [ ] Use HTTPS/TLS for all external connections
- [ ] Enable CSRF protection: `CSRF_TRUSTED_ORIGINS` properly set
- [ ] Use strong PostgreSQL password (20+ characters, mixed case, numbers, symbols)
- [ ] Enable PostgreSQL SSL: `sslmode=require` in `DATABASE_URL`
- [ ] Rotate Redis password and use AUTH
- [ ] Implement rate limiting on API endpoints
- [ ] Set up firewall rules: only allow necessary ports (80, 443, 5432 from app servers)
- [ ] Enable audit logging for sensitive operations (job deletion, user creation)
- [ ] Use managed secrets service (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault)
- [ ] Configure automated backups for PostgreSQL (daily, 30-day retention)
- [ ] Implement OAuth2 / SAML for user authentication (disable local password auth if possible)
- [ ] Set up DDoS protection (CloudFlare, AWS Shield)
- [ ] Enable container image scanning for vulnerabilities
- [ ] Configure network policies in Kubernetes (deny-all by default, whitelist required traffic)

---

## Summary

RenderHive can be run locally in **5 minutes** with Docker Compose, or scaled to production Kubernetes with proper configuration. Start with the Docker Compose setup, then adapt for your infrastructure.

For additional help:

- **API Documentation**: http://localhost:8000/api/schema/swagger/
- **Architecture**: See [02-architecture.md](02-architecture.md)
- **Troubleshooting**: See [14-troubleshooting.md](14-troubleshooting.md)
