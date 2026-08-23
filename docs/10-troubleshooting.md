# Troubleshooting Guide

## Common Issues & Solutions

---

## DOCKER & DEPLOYMENT

### Issue: `docker-compose up` fails with "permission denied"

**Symptoms**:

```
ERROR: denied while trying to connect to the Docker daemon
```

**Solution**:

```bash
# On Linux, add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# On Windows/Mac, ensure Docker Desktop is running
docker ps  # Should list containers
```

---

### Issue: PostgreSQL won't start

**Symptoms**:

```
postgres_1 | FATAL: could not open file "/var/lib/postgresql/data/postgresql.conf"
```

**Solution**:

```bash
# Delete existing volume and restart
docker-compose down -v
docker-compose up -d

# Or manually clear volume
docker volume rm renderhive_postgres_data
docker-compose up -d
```

---

### Issue: API can't connect to PostgreSQL

**Symptoms**:

```
api_1       | OperationalError: could not connect to server: Connection refused
```

**Solution**:

```bash
# Check PostgreSQL is healthy
docker-compose ps postgres

# Check DATABASE_URL in .env
echo $DATABASE_URL

# Should be: postgres://postgres:postgres@postgres:5432/renderhive

# Verify from inside API container
docker-compose exec api psql -h postgres -U postgres -d renderhive
```

---

### Issue: Redis connection refused

**Symptoms**:

```
ConnectionError: Error 111 connecting to redis://redis:6379/1. Connection refused.
```

**Solution**:

```bash
# Restart Redis
docker-compose restart redis

# Test connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# Check REDIS_URL in .env
echo $REDIS_URL
# Should be: redis://redis:6379/1
```

---

## DATABASE

### Issue: Migrations not applied

**Symptoms**:

```
Table "jobs_job" does not exist
```

**Solution**:

```bash
# Run migrations manually
docker-compose exec api python manage.py migrate

# Check migration status
docker-compose exec api python manage.py showmigrations

# If stuck, reset (dev only):
docker-compose exec api python manage.py migrate jobs zero
docker-compose exec api python manage.py migrate
```

---

### Issue: Superuser not created

**Symptoms**:

```
admin login fails, no users exist
```

**Solution**:

```bash
# Create superuser manually
docker-compose exec api python manage.py createsuperuser

# Or set env vars for auto-creation:
# DJANGO_SUPERUSER_USERNAME=admin
# DJANGO_SUPERUSER_EMAIL=admin@local
# DJANGO_SUPERUSER_PASSWORD=admin
docker-compose down
docker-compose up -d
```

---

## BACKEND / API

### Issue: `/api/jobs/` returns 401 Unauthorized

**Symptoms**:

```
curl http://localhost:8000/api/jobs/
{
  "detail": "Authentication credentials were not provided."
}
```

**Solution**:

```bash
# For browser: login at http://localhost:3000/auth/login

# For API: include Authorization header
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  http://localhost:8000/api/jobs/

# Generate token:
docker-compose exec api python manage.py shell
>>> from apps.users.models import UserProfile
>>> profile = UserProfile.objects.first()
>>> profile.api_token
'sk_live_...'
```

---

### Issue: CORS errors when calling API from frontend

**Symptoms**:

```
Access-Control-Allow-Origin header missing
```

**Solution**:

```bash
# Update .env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Restart API
docker-compose restart api

# Verify
curl -i http://localhost:8000/api/jobs/ | grep Access-Control
```

---

### Issue: Celery tasks not running

**Symptoms**:

```
Tasks stay in PENDING state forever
Dispatch doesn't happen
```

**Solution**:

```bash
# Check Celery worker is running
docker-compose ps celery-worker

# View logs
docker-compose logs -f celery-worker

# Manually trigger dispatch (dev only):
docker-compose exec api python manage.py shell
>>> from apps.jobs.tasks import dispatch_ready_tasks
>>> dispatch_ready_tasks()

# Restart Celery
docker-compose restart celery-worker
docker-compose restart celery-beat
```

---

### Issue: `ImportError: No module named...`

**Symptoms**:

```
ModuleNotFoundError: No module named 'apps.jobs'
```

**Solution**:

```bash
# Verify PYTHONPATH includes backend/
docker-compose exec api python -c "import sys; print(sys.path)"

# Reinstall dependencies
docker-compose exec api pip install -e .

# Rebuild container
docker-compose build --no-cache api
docker-compose up -d api
```

---

### Issue: Tasks not dispatching even though READY

**Symptoms**:

```
Job.ready_tasks > 0 but no tasks move to RUNNING
```

**Solution**:

```python
# Debug in Django shell
docker-compose exec api python manage.py shell

# Check for READY tasks
>>> from apps.jobs.models import Task
>>> Task.objects.filter(state='READY').count()
5  # If > 0, tasks should be dispatching

# Check for available workers
>>> from apps.workers.models import Worker
>>> Worker.objects.filter(state='ONLINE').count()
0  # AH-HA! No workers online

# Check worker health
>>> Worker.objects.all().values('name', 'state', 'last_heartbeat')

# If workers stale (>30 seconds), they're marked OFFLINE
>>> import datetime
>>> now = datetime.datetime.now(datetime.timezone.utc)
>>> stale_threshold = now - datetime.timedelta(seconds=30)
>>> Worker.objects.filter(last_heartbeat__lt=stale_threshold)
```

**Action**:

- Start a worker (see [Part D: Deploy Worker Application](03-setup.md#part-d-deploy-worker-application))
- Or register a test worker via API
- Or simulate worker heartbeat

---

## FRONTEND

### Issue: Dashboard won't load

**Symptoms**:

```
http://localhost:3000 shows blank page or 500 error
```

**Solution**:

```bash
# Check frontend container is running
docker-compose ps frontend

# View logs
docker-compose logs -f frontend

# Verify NEXT_PUBLIC_API_URL is set
docker-compose exec frontend env | grep NEXT_PUBLIC

# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

---

### Issue: API calls from frontend fail with 404

**Symptoms**:

```
GET http://localhost:8000/api/jobs/ returns 404
```

**Solution**:

```bash
# Check API is running and healthy
curl http://localhost:8000/health/

# Check API logs
docker-compose logs api

# Verify API base URL
# Dashboard should use: http://localhost:8000
# NOT: http://api:8000 (that's container-internal)

# Check frontend env var
docker-compose exec frontend env | grep NEXT_PUBLIC_API_URL
# Should show: NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

### Issue: WebSocket connection fails

**Symptoms**:

```
WebSocket failed to connect: Error during WebSocket handshake
```

**Solution**:

```bash
# Check WebSocket endpoint exists
curl http://localhost:8000/api/ws/

# Should return 400 (WebSocket upgrade required) or similar

# Check API ASGI is enabled (for WebSocket support)
# Verify docker-compose.yml has correct command for API

# Test WebSocket directly
python -c "
import asyncio, websockets, json

async def test():
    uri = 'ws://localhost:8000/api/ws/?token=sk_live_YOUR_TOKEN'
    async with websockets.connect(uri) as ws:
        print('Connected!')
        msg = await ws.recv()
        print(f'Received: {msg}')

asyncio.run(test())
"

# If fails, check ASGI config:
# backend/config/asgi.py should have ProtocolTypeRouter with WebSocket
```

---

## WORKERS

### Issue: Worker can't connect to API

**Symptoms**:

```
Worker status: DISCONNECTED
Unable to fetch tasks
```

**Solution**:

```bash
# 1. Verify API is accessible from worker machine
ping localhost  # or server hostname

# 2. Check API URL in worker config
cat ~/.renderhive/config.json
# "api_url" should be correct

# 3. Test connectivity
curl http://localhost:8000/health/

# 4. Verify authentication token
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/workers/me/

# 5. Check firewall (if remote)
telnet localhost 8000
# Should succeed (not "connection refused")

# 6. Restart worker application
ps aux | grep "worker/app.py"
kill -9 PID
python app.py
```

---

### Issue: Worker offline after 30 seconds

**Symptoms**:

```
Worker shows "ONLINE" briefly, then "OFFLINE"
Tasks get reassigned back to READY
```

**Solution**:

```bash
# Check worker heartbeat interval
cat ~/.renderhive/config.json | grep heartbeat_interval_sec
# Should be: 5 (send heartbeat every 5 seconds)

# Check network latency
ping server.renderhive.local
# Should be <50ms

# View worker logs
tail -f /path/to/renderhive/logs/worker.log

# Increase heartbeat timeout (backend config)
# In settings/base.py:
WORKER_STALE_THRESHOLD_SECONDS = 60  # was 30

# Restart API
docker-compose restart api
```

---

### Issue: Tasks fail on worker with "File not found"

**Symptoms**:

```
Render error: /project/textures/diffuse.tx not found
```

**Solution**:

```bash
# 1. Verify file exists
ls -la /project/textures/diffuse.tx

# 2. Check file permissions
chmod +r /project/textures/diffuse.tx

# 3. If file is on network, check mount point
mount | grep /project
# Should show network mount

# 4. Temporarily copy file to worker
scp /project/textures/diffuse.tx render-node-01:/local/cache/

# 5. Update scene to use local path
# Or update Maya plugin to auto-stage files

# 6. Set task environment to include file search paths
# In task execution:
export MAYA_IMAGE_PATH="/local/cache:$MAYA_IMAGE_PATH"
render.exe ...
```

---

### Issue: Worker using too much memory

**Symptoms**:

```
Telemetry: memory_usage_gb: 28.0 / 32.0
OOM killer may terminate renders
```

**Solution**:

```bash
# 1. Reduce max_concurrent_tasks
# In ~/.renderhive/config.json:
"max_concurrent_tasks": 1  # was 2 or more

# Restart worker
python app.py

# 2. Increase worker RAM (hardware upgrade)

# 3. Split renders into smaller frame batches
# Submit tasks with fewer frames per task:
# Task 1: frames 1-5 (instead of 1-10)
# Task 2: frames 6-10

# 4. Monitor memory per-task
# Add memory limit to render command:
# (DCC-specific, e.g., Houdini CPUS_PER_TASK=1)
```

---

## MAYA PLUGIN

### Issue: RenderHive menu doesn't appear in Maya

**Symptoms**:

```
Menu → RenderHive not found
```

**Solution**:

```bash
# 1. Verify plugin installation
ls ~/Maya/modules/RenderHive.mod

# 2. Check module file content
cat ~/Maya/modules/RenderHive.mod
# Should have correct path to plugin directory

# 3. Restart Maya

# 4. Enable plugin in Maya
# Window → Plug-in Manager
# Search "RenderHive"
# Check "Loaded" and "Auto load"

# 5. Load manually from script
python -c "
import maya.cmds as cmds
from renderhive_maya_submitter import add_menu
add_menu()
"

# 6. Check console for errors
# Window → General Editors → Script Editor
# Look for RenderHive initialization errors
```

---

### Issue: Scene validation fails repeatedly

**Symptoms**:

```
"File not found" error on every validation
```

**Solution**:

```python
# In Maya script editor:

import maya.cmds as cmds

# 1. Get scene path
scene_file = cmds.file(q=True, sn=True)
print(f"Scene: {scene_file}")

# 2. Check project
project_path = cmds.workspace(q=True, dir=True)
print(f"Project: {project_path}")

# 3. Check file references
refs = cmds.file(q=True, reference=True)
for ref in refs:
    path = cmds.referenceQuery(ref, filename=True)
    print(f"Ref: {ref} → {path}")
    print(f"  Exists: {os.path.exists(path)}")

# 4. Fix: use workspace-relative paths
# OR use Edit → Reexport All References
```

---

### Issue: Job submits but disappears from dashboard

**Symptoms**:

```
"✓ Job submitted: job-uuid"
But no job visible in dashboard
```

**Solution**:

```bash
# 1. Check job actually created in backend
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/jobs/

# Look for job with timestamp matching submission

# 2. Check API logs for errors
docker-compose logs api | grep "job-uuid"

# 3. If job created but hidden from dashboard:
# Dashboard may be filtering by:
# - state (PENDING by default shows all)
# - project name
# - department name
# Try removing all filters

# 4. Check WebSocket connection
# Open browser console (F12)
# Check for WebSocket errors
```

---

## PERFORMANCE

### Issue: Dashboard sluggish, takes >5 seconds to load job list

**Symptoms**:

```
Page takes long to render
Job list pagination slow
```

**Solution**:

```bash
# 1. Check API response time
curl -o /dev/null -s -w "%{time_total}\n" \
  http://localhost:8000/api/jobs/?limit=20

# Should be <500ms

# 2. If slow, check database indexes
docker-compose exec api python manage.py shell
>>> from django.db import connection
>>> connection.queries  # Shows SQL queries and timing

# 3. Add more database connections (if shared)
# In settings/base.py:
DATABASES['default']['CONN_MAX_AGE'] = 600  # 10 minutes

# 4. Enable caching
# CACHES['default']['TIMEOUT'] = 300  # 5 minutes

# 5. Reduce page size
# GET /api/jobs/?limit=10 (instead of 100)

# 6. Scale API replicas (production)
# Add more API pods/replicas
```

---

### Issue: Memory leak, API container RAM grows indefinitely

**Symptoms**:

```
docker stats shows api container using 2GB → 3GB → 4GB
Eventually OOM killed
```

**Solution**:

```bash
# 1. Find memory-intensive queries
docker-compose exec api python manage.py shell
>>> from django.db import connection
>>> connection.queries_log  # Enable query logging
>>> Task.objects.all().count()  # Heavy query
>>> Task.objects.filter(state='RUNNING').count()  # More efficient

# 2. Add pagination
# Ensure all list endpoints paginate (default: limit=20)

# 3. Restart API periodically (cron job)
# */6 * * * * docker-compose restart api

# 4. Upgrade to production config
# Gunicorn workers instead of Django dev server
# Proper memory management
```

---

### Issue: Celery tasks slow, job dispatch takes >10 seconds per task

**Symptoms**:

```
dispatch_ready_tasks() runs every 1 second but takes 8 seconds
Dispatch cycles bunch up and fall behind
```

**Solution**:

```bash
# 1. Profile Celery task
docker-compose exec api python manage.py shell
>>> import time
>>> from apps.jobs.tasks import dispatch_ready_tasks
>>> start = time.time()
>>> dispatch_ready_tasks()
>>> elapsed = time.time() - start
>>> print(f"Task took {elapsed:.2f} seconds")

# 2. If slow, check for:
# - Too many READY tasks (reduce by increasing frame batch size)
# - Inefficient database queries (add .select_related())
# - AI scheduler timeout (reduce timeout or disable)

# 3. Increase Celery worker concurrency
# In docker-compose.yml, celery-worker:
# command: celery -A config worker -c 8 -l info
# (8 = concurrency, increase to 16 or more)

# 4. Add more Celery workers
# Scale horizontally: run multiple celery-worker containers
```

---

## LOGGING & DEBUGGING

### Enable debug logging

```bash
# Set Django debug
export DEBUG=True

# Set logging level to DEBUG
export DJANGO_LOG_LEVEL=DEBUG

# Celery verbose logging
celery -A config worker -l debug

# Frontend debug mode
export NEXT_PUBLIC_LOG_LEVEL=debug
```

---

### Check application logs

```bash
# API logs
docker-compose logs -f api

# Celery worker logs
docker-compose logs -f celery-worker

# Frontend build logs
docker-compose logs -f frontend

# PostgreSQL logs
docker-compose logs -f postgres

# Redis logs
docker-compose logs -f redis

# Combine all
docker-compose logs -f
```

---

### Test connectivity between services

```bash
# From API container to PostgreSQL
docker-compose exec api psql -h postgres -U postgres -d renderhive -c "SELECT 1"

# From API container to Redis
docker-compose exec api redis-cli -h redis -n 1 ping

# From API container to Frontend
docker-compose exec api curl http://frontend:3000/

# From Frontend to API
docker-compose exec frontend curl http://api:8000/api/jobs/
```

---

## Contacting Support

If issues persist:

1. **Collect diagnostics**:

   ```bash
   docker-compose logs > logs.txt
   docker-compose ps > status.txt
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/health/ > health.json
   ```

2. **Check documentation**: [Full documentation index](01-overview.md)

3. **Open issue on GitHub**: https://github.com/your-org/renderhive/issues
   - Include: logs.txt, status.txt, health.json
   - Describe steps to reproduce

4. **Contact development team**: contact@renderhive.io

---

This troubleshooting guide covers 90% of common issues. For specialized problems, refer to component-specific documentation or reach out to the development team.
