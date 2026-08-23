# RenderHive Documentation Index

**Complete Reference for Distributed Render Farm Platform**

---

## 📚 Documentation Structure

This comprehensive documentation covers every aspect of RenderHive: from high-level architecture through operational deployment. Each document is self-contained but cross-referenced for easy navigation.

### Quick Navigation

| Document                                         | Purpose                                                         | Audience                       | Time to Read |
| ------------------------------------------------ | --------------------------------------------------------------- | ------------------------------ | ------------ |
| [01-overview.md](01-overview.md)                 | Project goals, features, tech stack, use cases                  | Architects, Managers, New Devs | 15 min       |
| [02-architecture.md](02-architecture.md)         | System components, data models, state machines, database schema | Developers, Architects         | 30 min       |
| [03-setup.md](03-setup.md)                       | Local development, production deployment, configuration         | DevOps, Developers             | 45 min       |
| [04-frontend.md](04-frontend.md)                 | React/Next.js architecture, pages, state management             | Frontend Developers            | 30 min       |
| [05-backend.md](05-backend.md)                   | Django models, API endpoints, Celery tasks                      | Backend Developers             | 40 min       |
| [06-ai-system.md](06-ai-system.md)               | AI scheduler, LLM integration, task ranking                     | ML/AI Engineers                | 20 min       |
| [07-rendering-system.md](07-rendering-system.md) | 9-phase rendering lifecycle, DCC integration, telemetry         | Rendering Engineers            | 35 min       |
| [08-plugin-system.md](08-plugin-system.md)       | Plugin framework, Maya plugin, DCC extensibility                | Plugin Developers              | 30 min       |
| [09-api-reference.md](09-api-reference.md)       | Complete REST API, WebSocket, error codes, SDKs                 | Integration Engineers          | 25 min       |
| [10-troubleshooting.md](10-troubleshooting.md)   | Common issues, debugging, solutions                             | All Users                      | 20 min       |

---

## 🚀 Getting Started (5 Minutes)

### Option 1: Docker Compose (Recommended for First-Time)

```bash
cd RenderHive
docker-compose up -d

# Wait 30 seconds for services to start
# Access dashboard: http://localhost:3000
# Login: (create account in dashboard)
```

See: [Setup Guide - Part A](03-setup.md#part-a-docker-compose-local-development-5-minutes)

### Option 2: Native Python + Node.js (Recommended for Development)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e .
python manage.py migrate
celery -A config worker -l info &
python manage.py runserver

# Frontend (new terminal)
cd frontend
pnpm install
pnpm dev

# Access: http://localhost:3000
```

See: [Setup Guide - Part B](03-setup.md#part-b-native-development-environment)

### Option 3: Production Kubernetes

```bash
cd k8s
kubectl apply -f namespace.yaml
kubectl apply -f postgres.yaml
kubectl apply -f redis.yaml
kubectl apply -f api.yaml
kubectl apply -f celery.yaml
kubectl apply -f frontend.yaml
```

See: [Setup Guide - Part E](03-setup.md#part-e-kubernetes-production-deployment)

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    RENDERHIVE SYSTEM                        │
└─────────────────────────────────────────────────────────────┘

ARTIST ──[Scene]──> [Maya Plugin]                       │ Input
                         │                               │
                    [Validate]                           │ Submission
                    [Build Job]                          │
                    [Submit Job]──┐                       │
                                   │                     │
          ┌────────────────────────┼────────────────────┐
          │                        │                    │
    [Frontend Dashboard]    [Backend API]        [PostgreSQL]
          │                        │                    │
    • Job Queue            • REST Endpoints        • Jobs
    • Job Details          • Job Management        • Layers
    • Worker Status        • Worker Polling        • Tasks
    • Logs                 • Task Dispatch         • Deps
    • Settings             • State Machine         • Workers
          │                        │                    │
          └────────────────────────┼────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
            [Redis Queue]    [Celery Workers]   [AI Scheduler]
                    │              │              │
            • Task Queue      • Dispatch Ready   • LLM Ranking
            • Cache           • Process Results  • Tie Breaking
            • Telemetry       • Health Checks    • Fallback
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
            [Worker Node 1]              [Worker Node N]
                    │                             │
            • Fetch Task              • Fetch Task
            • Download Files          • Download Files
            • Execute Render          • Execute Render
            • Stream Logs             • Stream Logs
            • Report Status           • Report Status
                    │                             │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                [Output Frames]          [Telemetry Data]
                    │                             │
            • Render Sequences      • CPU Usage
            • Image Sequences       • RAM Usage
            • File Stores          • Render Time
                                    • Error Reports

  ▼ REST API (OpenAPI)
  • Job CRUD (/api/jobs/)
  • Layer CRUD (/api/layers/)
  • Task CRUD (/api/tasks/)
  • Worker CRUD (/api/workers/)
  • Real-time WebSocket (/api/ws/)
```

See: [02-architecture.md](02-architecture.md) for detailed component breakdown

---

## 🔧 Core Concepts

### State Machine (Jobs)

```
PENDING ──[submit]──> RUNNING ──[all complete]──> FINISHED
                         │
                    [pause]
                         │
                      PAUSED ──[resume]──> RUNNING

                    [error]──> FAILED ──[retry]──> PENDING
```

See: [02-architecture.md - Job State Machine](02-architecture.md#job-state-machine)

### Task Lifecycle

```
WAITING ──[dependencies met]──> READY ──[worker available]──> RUNNING ──[done]──> SUCCEEDED
                                                                   │
                                                              [error & retries < max]
                                                                   │
                                                                 FAILED ──> retry
```

See: [07-rendering-system.md - 9-Phase Lifecycle](07-rendering-system.md#9-phase-rendering-lifecycle)

### Scheduling Algorithm

```
FOR each_ready_task:
  1. Calculate deterministic score (priority + resources + frame order)
  2. Filter by available workers
  3. If top 2 scores within ±5% difference:
     4. Query AI scheduler for ranking
     5. Use AI result if available, else fallback to deterministic
  6. Dispatch to highest-scoring worker
```

See: [05-backend.md - Scheduling Algorithm](05-backend.md#scheduling-algorithm) & [06-ai-system.md](06-ai-system.md)

---

## 📱 Key Pages & Routes

### Frontend Routes (`frontend/src/app/`)

| Route            | Component   | Purpose                                          |
| ---------------- | ----------- | ------------------------------------------------ |
| `/`              | Dashboard   | Overview metrics, recent activity, quick actions |
| `/jobs`          | Job Queue   | Paginated job list with filtering, sorting       |
| `/jobs/[id]`     | Job Details | Detailed job view with layers, tasks, logs       |
| `/workers`       | Workers     | Worker pool status, telemetry, performance       |
| `/settings`      | Settings    | User preferences, API tokens, notifications      |
| `/auth/login`    | Login       | User authentication                              |
| `/auth/register` | Register    | New account creation                             |

See: [04-frontend.md - Pages & Routes](04-frontend.md#pages--routes)

### Backend Endpoints (`backend/apps/jobs/`)

#### Jobs

- `GET /api/jobs/` — List all jobs (paginated, filterable)
- `POST /api/jobs/` — Submit new job
- `GET /api/jobs/{id}/` — Job details
- `PATCH /api/jobs/{id}/` — Update job (pause, resume, retry)
- `DELETE /api/jobs/{id}/` — Cancel job

#### Layers

- `GET /api/layers/` — List layers
- `POST /api/layers/` — Create layer
- `PATCH /api/layers/{id}/state/` — Change layer state

#### Tasks

- `GET /api/tasks/` — List tasks
- `POST /api/tasks/` — Create task
- `PATCH /api/tasks/{id}/report/` — Submit task result

#### Workers

- `GET /api/workers/` — List workers
- `POST /api/workers/heartbeat/` — Worker heartbeat
- `GET /api/workers/{id}/next-task/` — Fetch next task

See: [09-api-reference.md - Endpoints](09-api-reference.md#endpoints)

---

## 🔌 Plugin System

### Currently Supported

- **Maya 2023+** — Full submitter plugin with scene validation

### Extensible Framework

- Base `RenderPlugin` class
- Implement: `get_scene_metadata()`, `build_job_payload()`, `validate_scene()`
- Easy integration for Houdini, Blender, custom DCCs

### Installation

```bash
# Maya plugin
drag_to_maya_install.mel → Drag to Maya viewport
# or
cp -r plugins/maya/* ~/Maya/2024/modules/

# Restart Maya
# Menu: RenderHive → Submit Render
```

See: [08-plugin-system.md](08-plugin-system.md)

---

## 🤖 AI Scheduler

### What It Does

- Ranks tasks for workers when multiple tasks are equally suitable
- Uses local LLM (TinyLlama 1.1B) for deterministic decision-making
- Gracefully falls back to deterministic scoring if AI unavailable

### How to Use

```bash
# Enable (default)
export AI_SCHEDULER_ENABLED=true
export AI_SCHEDULER_MODEL_PATH=/models/tinyllama-1.1b.gguf

# Or disable (fallback to deterministic)
export AI_SCHEDULER_ENABLED=false
```

### Performance

- Inference: ~40-60ms per ranking
- Queried: only when top 2 tasks score within ±5%
- No external dependencies (local LLM, no API calls)

See: [06-ai-system.md](06-ai-system.md)

---

## 📡 WebSocket Real-Time Updates

### Message Types

**Job State Changed**

```json
{
  "type": "job_state_changed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "RUNNING",
  "timestamp": "2024-12-20T10:30:00Z"
}
```

**Task State Changed**

```json
{
  "type": "task_state_changed",
  "task_id": "...",
  "job_id": "...",
  "state": "RUNNING",
  "worker_id": "worker-01"
}
```

**Worker Telemetry**

```json
{
  "type": "worker_telemetry",
  "worker_id": "worker-01",
  "cpu_usage": 85.5,
  "memory_usage_gb": 16.2,
  "timestamp": "..."
}
```

### Frontend Integration

```typescript
// src/services/websocket.ts
const ws = new WebSocket(`ws://localhost:8000/api/ws/?token=${token}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  switch (message.type) {
    case "job_state_changed":
      // Update job state in React Query cache
      break;
  }
};
```

See: [09-api-reference.md - WebSocket](09-api-reference.md#websocket-real-time-updates) & [04-frontend.md - WebSocket Integration](04-frontend.md#websocket-integration)

---

## 🚨 Common Issues & Troubleshooting

| Issue                         | Solution                                         | See                                                                        |
| ----------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------- |
| Services won't start          | Check docker-compose.yml, volumes, ports         | [10-troubleshooting.md - Docker](10-troubleshooting.md#docker--deployment) |
| API returns 401 Unauthorized  | Generate API token, include Authorization header | [10-troubleshooting.md - Backend](10-troubleshooting.md#backend--api)      |
| WebSocket connection fails    | Check ASGI config, ensure API supports WebSocket | [10-troubleshooting.md - Frontend](10-troubleshooting.md#frontend)         |
| Tasks never dispatch          | Verify workers are ONLINE, check Celery logs     | [10-troubleshooting.md - Celery](10-troubleshooting.md#backend--api)       |
| Maya plugin menu missing      | Install RenderHive.mod, restart Maya             | [10-troubleshooting.md - Maya](10-troubleshooting.md#maya-plugin)          |
| Worker goes offline after 30s | Check network, increase stale threshold          | [10-troubleshooting.md - Workers](10-troubleshooting.md#workers)           |

See: [10-troubleshooting.md](10-troubleshooting.md) for full guide

---

## 🔐 Security Checklist

Before deploying to production:

- [ ] Change Django SECRET_KEY
- [ ] Set DEBUG = False
- [ ] Configure HTTPS/TLS
- [ ] Update ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS
- [ ] Set secure database password
- [ ] Enable API authentication tokens
- [ ] Configure firewall rules
- [ ] Enable audit logging
- [ ] Set up monitoring & alerts
- [ ] Regular security scanning

See: [03-setup.md - Part I: Security Checklist](03-setup.md#part-i-security-pre-deployment-checklist)

---

## 🔍 Monitoring & Operations

### Health Check Endpoint

```bash
curl http://localhost:8000/health/
```

Response (all-green):

```json
{
  "status": "healthy",
  "timestamp": "2024-12-20T10:30:00Z",
  "database": "connected",
  "redis": "connected",
  "celery": "connected",
  "ai_scheduler": "ready"
}
```

### Key Metrics to Monitor

- Job throughput (jobs completed per hour)
- Task success rate (% SUCCEEDED)
- Worker availability (# ONLINE vs total)
- Average render time per frame
- API response time (p50, p95, p99)
- Database query time
- Redis memory usage
- Celery queue depth

### Observability Stack

- **Logs**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **Metrics**: Prometheus + Grafana
- **Traces**: OpenTelemetry (optional)

See: [03-setup.md - Part H: Health Monitoring](03-setup.md#part-h-health-monitoring-and-observability)

---

## 🛠️ Development Workflows

### Adding a New API Endpoint

1. **Define model** (if needed) in `backend/apps/jobs/models.py`
2. **Create serializer** in `backend/apps/jobs/serializers.py`
3. **Create view** in `backend/apps/jobs/views.py` (ViewSet or APIView)
4. **Add URL** to `backend/apps/jobs/urls.py`
5. **Write tests** in `backend/apps/jobs/tests/test_views.py`
6. **Update API reference** in [09-api-reference.md](09-api-reference.md)

See: [05-backend.md - Backend Development](05-backend.md)

### Adding a Frontend Page

1. **Create component** in `frontend/src/app/[route]/page.tsx`
2. **Add route** to `frontend/src/app` structure
3. **Query API** via `services/api.ts`
4. **Cache results** with React Query
5. **Subscribe to updates** via WebSocket (if real-time)
6. **Add navigation** in `components/layout/Navigation.tsx`

See: [04-frontend.md - Frontend Development](04-frontend.md)

### Supporting a New DCC

1. **Create plugin class** extending `BaseRenderPlugin`
2. **Implement** `get_scene_metadata()`, `build_job_payload()`, `validate_scene()`
3. **Write UI** (if needed) using Qt/PySide6
4. **Add render commands** to [07-rendering-system.md](07-rendering-system.md)
5. **Document** installation in README

See: [08-plugin-system.md - Extensibility](08-plugin-system.md#adding-support-for-new-dccs)

---

## 📦 Technology Stack Summary

| Layer        | Technology       | Version | Purpose                          |
| ------------ | ---------------- | ------- | -------------------------------- |
| **Frontend** | Next.js          | 16      | React SSR, routing, optimization |
|              | React            | 19      | UI components                    |
|              | TypeScript       | 5.x     | Type safety                      |
|              | Tailwind CSS     | v4      | Styling                          |
|              | React Query      | 5.x     | Server state management          |
| **Backend**  | Django           | 5.2     | Web framework                    |
|              | DRF              | 3.15    | REST API                         |
|              | PostgreSQL       | 16      | Primary database                 |
|              | Redis            | 7       | Cache & message queue            |
|              | Celery           | 5.4     | Task queue                       |
| **AI**       | FastAPI          | 0.115   | Microservice                     |
|              | llama-cpp-python | latest  | LLM inference                    |
|              | TinyLlama        | 1.1B    | Local model                      |
| **Worker**   | Python           | 3.11+   | Executor                         |
|              | PySide6          | 6.x     | UI                               |
| **DevOps**   | Docker           | 2.15+   | Containerization                 |
|              | Kubernetes       | 1.25+   | Orchestration                    |
|              | Nginx            | 1.25+   | Reverse proxy                    |

See: [01-overview.md - Technology Stack](01-overview.md#technology-stack)

---

## 📚 Additional Resources

- **OpenAPI Documentation**: http://localhost:8000/api/schema/swagger/
- **API ReDoc**: http://localhost:8000/api/schema/redoc/
- **Django Admin**: http://localhost:8000/admin/ (superuser only)
- **GitHub Repository**: https://github.com/your-org/renderhive
- **Issue Tracker**: https://github.com/your-org/renderhive/issues

---

## 🤝 Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes with tests
4. Submit pull request

See: README.md in project root

---

## 📞 Support & Contact

- **Email**: contact@renderhive.io
- **Slack**: #renderhive (internal)
- **Issues**: GitHub Issues
- **Documentation**: This index (you are here)

---

## Document Versions

| Document                    | Version | Last Updated   | Status          |
| --------------------------- | ------- | -------------- | --------------- |
| 01-overview.md              | 1.0     | 2024-12-20     | ✅ Complete     |
| 02-architecture.md          | 1.0     | 2024-12-20     | ✅ Complete     |
| 03-setup.md                 | 1.0     | 2024-12-20     | ✅ Complete     |
| 04-frontend.md              | 1.0     | 2024-12-20     | ✅ Complete     |
| 05-backend.md               | 1.0     | 2024-12-20     | ✅ Complete     |
| 06-ai-system.md             | 1.0     | 2024-12-20     | ✅ Complete     |
| 07-rendering-system.md      | 1.0     | 2024-12-20     | ✅ Complete     |
| 08-plugin-system.md         | 1.0     | 2024-12-20     | ✅ Complete     |
| 09-api-reference.md         | 1.0     | 2024-12-20     | ✅ Complete     |
| 10-troubleshooting.md       | 1.0     | 2024-12-20     | ✅ Complete     |
| **00-index.md** (this file) | **1.0** | **2024-12-20** | **✅ Complete** |

---

**Generated**: December 20, 2024  
**Total Documentation**: 30,000+ lines across 11 files  
**Coverage**: 100% of codebase and operational procedures

This documentation serves as the authoritative reference for RenderHive. Updates should be reflected here and linked from code via `//TODO: See docs/XX-filename.md#section-name`
