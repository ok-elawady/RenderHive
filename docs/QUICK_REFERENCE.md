# RenderHive Quick Reference Card

**Print this page or bookmark for quick access to common commands and links.**

---

## 🚀 Quick Start (Choose One)

### Docker Compose (5 minutes)

```bash
cd RenderHive
docker-compose up -d
# Access: http://localhost:3000
```

### Native Development

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -e . && python manage.py migrate
celery -A config worker &
python manage.py runserver

# Frontend (new terminal)
cd frontend && pnpm install && pnpm dev
```

### Production (Kubernetes)

```bash
cd k8s
kubectl apply -f namespace.yaml
kubectl apply -f postgres.yaml
kubectl apply -f api.yaml
kubectl apply -f celery.yaml
kubectl apply -f frontend.yaml
```

---

## 📡 Essential URLs

| Service   | URL                                          | Purpose                        |
| --------- | -------------------------------------------- | ------------------------------ |
| Dashboard | http://localhost:3000                        | Job queue, details, monitoring |
| API       | http://localhost:8000                        | REST endpoints                 |
| Admin     | http://localhost:8000/admin                  | Django admin                   |
| API Docs  | http://localhost:8000/api/schema/swagger/    | Swagger UI                     |
| Health    | http://localhost:8000/health/                | System status                  |
| WebSocket | ws://localhost:8000/api/ws/?token=YOUR_TOKEN | Real-time updates              |

---

## 🔑 Key Credentials (Local Dev)

| Service      | Username         | Password              | How to Set                    |
| ------------ | ---------------- | --------------------- | ----------------------------- |
| Django Admin | admin            | admin                 | See docs/03-setup.md - Part A |
| API Token    | (auto-generated) | (copy from dashboard) | Dashboard → Settings          |
| PostgreSQL   | postgres         | postgres              | .env file                     |

---

## 📋 Essential Commands

### Docker Compose

```bash
docker-compose up -d                # Start all services
docker-compose down                 # Stop all services
docker-compose logs -f api          # Follow API logs
docker-compose ps                   # Show container status
docker-compose exec api bash        # Shell into container
```

### Database

```bash
docker-compose exec api python manage.py migrate           # Apply migrations
docker-compose exec api python manage.py createsuperuser  # Create admin user
docker-compose exec api python manage.py shell            # Django shell
docker-compose exec postgres psql -U postgres -d renderhive  # PostgreSQL shell
```

### Celery

```bash
docker-compose logs -f celery-worker    # Watch Celery logs
docker-compose restart celery-worker    # Restart Celery
docker-compose restart celery-beat      # Restart scheduler
```

### Frontend

```bash
cd frontend
pnpm install              # Install dependencies
pnpm dev                  # Development server (hot reload)
pnpm build                # Production build
pnpm lint                 # Run ESLint
```

### Backend

```bash
cd backend
pip install -e .          # Install dependencies
python manage.py runserver                # Development server
python manage.py test                     # Run tests
python manage.py makemigrations           # Create migrations
python manage.py migrate                  # Apply migrations
```

---

## 🔍 Debugging

### Check Service Health

```bash
# API health
curl http://localhost:8000/health/

# Redis
docker-compose exec redis redis-cli ping

# PostgreSQL
docker-compose exec postgres psql -U postgres -d renderhive -c "SELECT 1"

# Celery
docker-compose logs celery-worker | grep "ready"
```

### Common Issues Quick Fixes

| Issue                    | Command                                                    |
| ------------------------ | ---------------------------------------------------------- |
| Services won't start     | `docker-compose down -v && docker-compose up -d`           |
| Database error           | `docker-compose exec api python manage.py migrate`         |
| No superuser             | `docker-compose exec api python manage.py createsuperuser` |
| Celery tasks not running | `docker-compose restart celery-worker celery-beat`         |
| Frontend not loading     | `docker-compose logs frontend`                             |
| API 404 errors           | `curl http://localhost:8000/api/jobs/`                     |

---

## 📚 Documentation Quick Links

| Need                 | Document               | Section           |
| -------------------- | ---------------------- | ----------------- |
| Project overview     | 01-overview.md         | Top               |
| Setup locally        | 03-setup.md            | Part A            |
| Deploy to Kubernetes | 03-setup.md            | Part E            |
| First render job     | 03-setup.md            | Part C            |
| Frontend development | 04-frontend.md         | Top               |
| Backend development  | 05-backend.md          | Top               |
| API endpoints        | 09-api-reference.md    | Endpoints         |
| Troubleshoot issue   | 10-troubleshooting.md  | Index by category |
| System architecture  | 02-architecture.md     | Components        |
| AI scheduler         | 06-ai-system.md        | Top               |
| Rendering phases     | 07-rendering-system.md | 9-Phase Lifecycle |
| Plugins              | 08-plugin-system.md    | Top               |

---

## 🔐 Authentication

### Generate API Token

```bash
# Via Django shell
docker-compose exec api python manage.py shell
>>> from apps.users.models import UserProfile
>>> profile = UserProfile.objects.first()
>>> profile.api_token
'sk_live_...'

# Or via API endpoint
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### Use API Token

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/jobs/
```

---

## 📊 Job Lifecycle

```
Submit (Artist)
    ↓
PENDING (Backend ingestion)
    ↓
RUNNING (Task dispatch)
    ↓
FINISHED (All tasks complete)
    ↓
FAILED (Retry or cancel)
```

**Monitor Progress**:

1. Dashboard: http://localhost:3000/jobs
2. API: `curl http://localhost:8000/api/jobs/{id}/`
3. WebSocket: Subscribe to job updates (see docs/09-api-reference.md)

---

## 🔌 Common API Endpoints

### Jobs

```bash
# List jobs
curl http://localhost:8000/api/jobs/?limit=20

# Get job details
curl http://localhost:8000/api/jobs/{id}/

# Submit job
curl -X POST http://localhost:8000/api/jobs/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...job payload...}'

# Pause job
curl -X PATCH http://localhost:8000/api/jobs/{id}/ \
  -H "Authorization: Bearer TOKEN" \
  -d '{"state": "PAUSED"}'

# Resume job
curl -X PATCH http://localhost:8000/api/jobs/{id}/ \
  -H "Authorization: Bearer TOKEN" \
  -d '{"state": "RUNNING"}'
```

### Workers

```bash
# List workers
curl http://localhost:8000/api/workers/

# Worker heartbeat (from worker)
curl -X POST http://localhost:8000/api/workers/heartbeat/ \
  -H "Authorization: Bearer TOKEN" \
  -d '{...telemetry...}'

# Get next task (from worker)
curl http://localhost:8000/api/workers/{id}/next-task/ \
  -H "Authorization: Bearer TOKEN"
```

### Tasks

```bash
# Report task completion (from worker)
curl -X PATCH http://localhost:8000/api/tasks/{id}/report/ \
  -H "Authorization: Bearer TOKEN" \
  -d '{"exit_code": 0, "duration_seconds": 120}'
```

---

## 🐛 Logs Location

| Service     | Log Location                        |
| ----------- | ----------------------------------- |
| API         | `docker-compose logs api`           |
| Celery      | `docker-compose logs celery-worker` |
| Frontend    | `docker-compose logs frontend`      |
| PostgreSQL  | `docker-compose logs postgres`      |
| Redis       | `docker-compose logs redis`         |
| Worker App  | `~/.renderhive/logs/worker.log`     |
| Maya Plugin | `~/Documents/maya/logs/`            |

---

## 📈 Performance Metrics

### Target Metrics

- Job dispatch latency: <5 seconds
- API response time (p95): <500ms
- Worker heartbeat: 5-second interval
- Task completion time: DCC-dependent
- System throughput: 10+ concurrent jobs

### Check Current Performance

```bash
# API response time
time curl http://localhost:8000/api/jobs/?limit=20

# Database query performance
docker-compose exec api python manage.py shell
>>> from django.db import connection
>>> connection.queries  # Enable query profiling
```

---

## 🔄 Database Backup & Restore

### Backup PostgreSQL

```bash
docker-compose exec postgres pg_dump -U postgres renderhive > backup.sql
```

### Restore PostgreSQL

```bash
docker-compose exec postgres psql -U postgres < backup.sql
```

### Reset Database (dev only)

```bash
docker-compose down -v
docker-compose up -d
docker-compose exec api python manage.py migrate
docker-compose exec api python manage.py createsuperuser
```

---

## 🐳 Docker Cheat Sheet

```bash
# Build specific service
docker-compose build api

# Force rebuild
docker-compose build --no-cache api

# Run command in container
docker-compose exec api python manage.py shell

# Scale service
docker-compose up -d --scale celery-worker=3

# View resource usage
docker stats

# Remove everything (dev only)
docker-compose down -v --remove-orphans

# Rebuild and restart
docker-compose up -d --force-recreate --build
```

---

## 🔐 Security Checklist

Before production deployment:

- [ ] Change Django SECRET_KEY
- [ ] Set DEBUG = False
- [ ] Enable HTTPS/TLS
- [ ] Update ALLOWED_HOSTS
- [ ] Configure CORS origins
- [ ] Set strong database password
- [ ] Enable API rate limiting
- [ ] Configure firewall rules
- [ ] Enable audit logging
- [ ] Setup monitoring & alerts

See: docs/03-setup.md - Part I

---

## 🎯 Common Tasks

### Submit a Render Job

1. Open Dashboard: http://localhost:3000
2. Click "Submit Job" or use Maya plugin
3. Select layers, set priority, click Submit
4. Monitor progress on Job Details page

### Add New API Endpoint

1. Define model in `backend/apps/jobs/models.py`
2. Create serializer in `backend/apps/jobs/serializers.py`
3. Create viewset in `backend/apps/jobs/views.py`
4. Add URL in `backend/apps/jobs/urls.py`
5. Test with `python manage.py test`

### Add Frontend Page

1. Create component in `frontend/src/app/[route]/page.tsx`
2. Import API client from `frontend/src/services/api.ts`
3. Use React Query for data fetching
4. Add navigation link to layout
5. Test with `pnpm dev`

### Deploy to Production

1. Follow docs/03-setup.md - Part E (Kubernetes)
2. Or use Docker Compose with prod config
3. Run docs/03-setup.md - Part I (Security checklist)
4. Enable monitoring per docs/03-setup.md - Part H

---

## 📞 Support

| Issue                | Resource                               |
| -------------------- | -------------------------------------- |
| Can't start services | docs/10-troubleshooting.md - Docker    |
| API errors           | docs/09-api-reference.md - Error Codes |
| Frontend issues      | docs/04-frontend.md                    |
| Backend issues       | docs/05-backend.md                     |
| Deployment issues    | docs/03-setup.md                       |
| Plugin issues        | docs/08-plugin-system.md               |
| Rendering issues     | docs/07-rendering-system.md            |
| General questions    | docs/00-index.md                       |

---

## 🎓 Learning Resources

- **Setup Tutorial**: docs/03-setup.md - Part A (5 minutes)
- **First Job**: docs/03-setup.md - Part C (15 minutes)
- **API Guide**: docs/09-api-reference.md (25 minutes)
- **Architecture**: docs/02-architecture.md (30 minutes)
- **Full Course**: Follow all role-specific docs (2-4 hours)

---

## 📋 File Structure

```
RenderHive/
├── backend/                 # Django API
├── frontend/                # Next.js dashboard
├── worker/                  # Render worker
├── plugins/
│   └── maya/               # Maya plugin
├── docker-compose.yml      # Local dev setup
├── docs/                   # THIS DOCUMENTATION
│   ├── 00-index.md         # Navigation hub
│   ├── 01-overview.md      # Project overview
│   ├── 02-architecture.md  # System design
│   ├── 03-setup.md         # Setup guide
│   ├── 04-frontend.md      # Frontend docs
│   ├── 05-backend.md       # Backend docs
│   ├── 06-ai-system.md     # AI scheduler
│   ├── 07-rendering-system.md
│   ├── 08-plugin-system.md
│   ├── 09-api-reference.md # API reference
│   └── 10-troubleshooting.md
├── k8s/                    # Kubernetes manifests
├── nginx/                  # Nginx config
└── README.md               # Project README
```

---

## 🌟 Pro Tips

1. **Save API token** in browser's localStorage for persistence
2. **Use Postman** for API testing and debugging
3. **Enable query logging** in Django for performance analysis
4. **Monitor Celery** queue depth for bottleneck detection
5. **Stream logs** with `docker-compose logs -f` while testing
6. **Use browser DevTools** to debug WebSocket messages
7. **Test locally** before deploying to production
8. **Keep docs updated** when modifying code
9. **Use version control** for all configuration changes
10. **Backup database** before major upgrades

---

**Last Updated**: December 20, 2024  
**Documentation Version**: 1.0  
**Print This**: Save as PDF bookmark for offline access

See [00-index.md](00-index.md) for full documentation.
