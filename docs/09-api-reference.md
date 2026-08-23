# API Reference Guide

## Authentication

### Token-Based Authentication (Worker/Plugin)

Tokens are used by workers and DCC plugins to authenticate with the API.

**Obtain Token**:

```bash
# Option 1: Generate via Django shell (development)
python manage.py shell
>>> from apps.users.models import UserProfile
>>> profile = UserProfile.objects.first()
>>> profile.api_token
'sk_live_abc123def456...'

# Option 2: Generate via API (requires logged-in session)
POST /api/users/me/generate-token/
Response:
{
  "token": "sk_live_abc123def456..."
}
```

**Use Token in Requests**:

```bash
curl -H "Authorization: Bearer sk_live_abc123def456..." \
  http://localhost:8000/api/jobs/

# Or (deprecated but still supported):
curl -H "Authorization: Token sk_live_abc123def456..." \
  http://localhost:8000/api/jobs/
```

### Session-Based Authentication (Browser)

Handled automatically by cookies. Login at `http://localhost:3000/auth/login`.

---

## REST API Endpoints

### Jobs

#### `GET /api/jobs/`

List all jobs (paginated).

**Query Parameters**:

- `page` (int, default=1) — Page number
- `limit` (int, default=20, max=100) — Results per page
- `search` (str) — Search by name or visible_name
- `state` (str) — Filter: PENDING, RUNNING, FINISHED, FAILED, PAUSED
- `project` (str) — Filter by project name
- `department` (str) — Filter by department
- `user` (str) — Filter by submitter username
- `priority__gte` (int) — Filter by minimum priority
- `priority__lte` (int) — Filter by maximum priority
- `ordering` (str) — Sort field: `created_at`, `-priority`, `state`

**Example**:

```bash
curl "http://localhost:8000/api/jobs/?state=RUNNING&priority__gte=70&limit=10"
```

**Response** (HTTP 200):

```json
{
  "count": 156,
  "next": "http://localhost:8000/api/jobs/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "ProjectName_ShotName_20250115",
      "visible_name": "ProjectName / ShotName",
      "project": "ProjectName",
      "department": "Lighting",
      "user": "john.doe",
      "submitted_by": null,
      "state": "RUNNING",
      "is_paused": false,
      "priority": 75,
      "max_tasks_per_worker": 1,
      "total_tasks": 100,
      "waiting_tasks": 0,
      "ready_tasks": 10,
      "running_tasks": 5,
      "succeeded_tasks": 85,
      "failed_tasks": 0,
      "skipped_tasks": 0,
      "depend_tasks": 0,
      "created_at": "2025-01-15T09:00:00Z",
      "updated_at": "2025-01-15T10:30:45Z",
      "stopped_at": null
    }
  ]
}
```

---

#### `POST /api/jobs/`

Create a new job.

**Request Body**:

```json
{
  "name": "ProjectName_ShotName_20250115_120000",
  "visible_name": "ProjectName / ShotName",
  "project": "ProjectName",
  "department": "Lighting",
  "user": "john.doe",
  "priority": 75,
  "max_tasks_per_worker": 1,
  "log_directory": "/storage/renderhive/logs/job-id/",
  "layers": [
    {
      "name": "beauty",
      "type": "RENDER",
      "order": 1,
      "render_layer_name": "beauty",
      "tasks": [
        { "frame_start": 1, "frame_end": 10, "max_retries": 3 },
        { "frame_start": 11, "frame_end": 20, "max_retries": 3 }
      ]
    }
  ],
  "dependencies": [],
  "included_pools": ["STUDIO_A"],
  "excluded_pools": []
}
```

**Response** (HTTP 201):

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "ProjectName_ShotName_20250115_120000",
  "state": "PENDING",
  "total_tasks": 2
}
```

**Error Responses**:

- `400 Bad Request` — Invalid payload (e.g., frame_end < frame_start)
- `400 Validation Error` — name not unique, priority out of range
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Not allowed to submit jobs (permission denied)

---

#### `GET /api/jobs/{id}/`

Retrieve a single job.

**Response** (HTTP 200):

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "ProjectName_ShotName_20250115_120000",
  # ... (same fields as list)
  "layers": [
    {
      "id": "layer-uuid",
      "name": "beauty",
      "type": "RENDER",
      "order": 1,
      "tasks": [
        {
          "id": "task-uuid-1",
          "layer_id": "layer-uuid",
          "frame_start": 1,
          "frame_end": 10,
          "state": "SUCCEEDED",
          "retry_count": 0,
          "max_retries": 3,
          "worker_id": "worker-uuid",
          "started_at": "2025-01-15T09:01:00Z",
          "completed_at": "2025-01-15T09:43:00Z",
          "exit_code": 0
        }
      ]
    }
  ]
}
```

---

#### `PATCH /api/jobs/{id}/`

Update a job (only certain fields).

**Allowed Fields**:

- `visible_name` (str)
- `priority` (int, 1-100)
- `is_paused` (bool)

**Request Body**:

```json
{
  "priority": 50,
  "is_paused": true
}
```

**Response** (HTTP 200): Updated job object

---

#### `POST /api/jobs/{id}/pause/`

Pause job execution.

**Response** (HTTP 200):

```json
{
  "id": "...",
  "state": "PAUSED"
}
```

Effect: Job.is_paused = True. Running tasks continue; new tasks not dispatched.

---

#### `POST /api/jobs/{id}/resume/`

Resume paused job.

**Response** (HTTP 200):

```json
{
  "id": "...",
  "state": "RUNNING"
}
```

Effect: Job.is_paused = False. Ready tasks re-enter dispatch queue.

---

#### `POST /api/jobs/{id}/retry_failed_tasks/`

Requeue all failed tasks.

**Request Body** (optional):

```json
{
  "max_retries": 2
}
```

**Response** (HTTP 200):

```json
{
  "retried_count": 3,
  "tasks": [
    { "id": "task-uuid-1", "state": "READY" },
    { "id": "task-uuid-2", "state": "READY" }
  ]
}
```

---

#### `DELETE /api/jobs/{id}/`

Delete job.

**Constraints**: Only if job.state == "PENDING"

**Response** (HTTP 204): No content

---

### Workers

#### `GET /api/workers/`

List all workers.

**Query Parameters**:

- `pool` (str) — Filter by pool name
- `state` (str) — Filter: ONLINE, OFFLINE, DISABLED

**Response** (HTTP 200):

```json
{
  "count": 8,
  "results": [
    {
      "id": "worker-uuid-1",
      "name": "render-node-01",
      "pool": "STUDIO_A",
      "state": "ONLINE",
      "capabilities": {
        "cpu_cores": 16,
        "memory_gb": 32,
        "gpu_count": 2,
        "gpu_memory_gb": [12.0, 12.0],
        "software": ["maya2024", "arnold7", "vray6"]
      },
      "telemetry": {
        "cpu_usage_percent": 45.2,
        "memory_usage_gb": 8.5,
        "memory_total_gb": 32.0,
        "gpu_count": 2,
        "gpu_memory_gb": [12.0, 12.0],
        "gpu_usage_percent": [75.0, 45.0],
        "network_latency_ms": 2.3
      },
      "last_heartbeat": "2025-01-15T10:45:12Z",
      "created_at": "2025-01-10T08:00:00Z",
      "updated_at": "2025-01-15T10:45:12Z"
    }
  ]
}
```

---

#### `POST /api/workers/heartbeat/`

Worker health check and telemetry update.

**Request Body**:

```json
{
  "worker_id": "worker-uuid-1",
  "telemetry": {
    "cpu_usage_percent": 45.2,
    "memory_usage_gb": 8.5,
    "memory_total_gb": 32.0,
    "gpu_count": 2,
    "gpu_memory_gb": [12.0, 12.0],
    "gpu_usage_percent": [75.0, 45.0]
  }
}
```

**Response** (HTTP 200):

```json
{
  "worker_id": "worker-uuid-1",
  "status": "ok",
  "next_task": {
    "id": "task-uuid",
    "layer_id": "layer-uuid",
    "frame_start": 1,
    "frame_end": 10,
    "render_command": "render -rl beauty -fs 1 -fe 10 scene.mb",
    "output_path": "/storage/renders/ProjectName/shot-001/",
    "max_retries": 3
  }
}
```

Note: `next_task` is null if no READY tasks available.

---

#### `POST /api/tasks/{task_id}/complete/`

Report task completion.

**Request Body**:

```json
{
  "exit_code": 0,
  "duration_seconds": 42.3,
  "peak_memory_gb": 8.9,
  "log_content": "V-Ray: Final render complete…"
}
```

**Response** (HTTP 200):

```json
{
  "task_id": "task-uuid",
  "state": "SUCCEEDED",
  "job_id": "job-uuid",
  "job_state": "RUNNING"
}
```

---

### Worker Pools

#### `GET /api/pools/`

List all worker pools.

**Response** (HTTP 200):

```json
{
  "results": [
    {
      "id": "pool-uuid-1",
      "name": "STUDIO_A",
      "description": "Main rendering pool - Studio A building",
      "created_at": "2025-01-10T08:00:00Z",
      "updated_at": "2025-01-15T10:45:12Z"
    },
    {
      "id": "pool-uuid-2",
      "name": "GPU_NODES",
      "description": "High-end GPU cluster",
      "created_at": "2025-01-10T08:00:00Z",
      "updated_at": "2025-01-15T10:45:12Z"
    }
  ]
}
```

---

#### `POST /api/pools/`

Create new worker pool.

**Request Body**:

```json
{
  "name": "REMOTE_RENDER",
  "description": "Remote render farm in cloud"
}
```

**Response** (HTTP 201): Pool object

---

### Users & Authentication

#### `GET /api/users/me/`

Get current user profile.

**Response** (HTTP 200):

```json
{
  "id": 1,
  "username": "john.doe",
  "email": "john.doe@company.com",
  "first_name": "John",
  "last_name": "Doe",
  "department": "Lighting",
  "api_token": "sk_live_abc123def456...",
  "preferences": {
    "theme": "dark",
    "email_notifications": true
  }
}
```

---

#### `POST /api/auth/login/`

Browser login.

**Request Body**:

```json
{
  "username": "john.doe",
  "password": "password123"
}
```

**Response** (HTTP 200):

```json
{
  "key": "auth-token-abc123..."
}
```

Sets session cookie automatically.

---

#### `POST /api/auth/logout/`

Logout (browser).

**Response** (HTTP 200):

```json
{
  "detail": "Successfully logged out"
}
```

---

#### `POST /api/users/me/change-password/`

Change user password.

**Request Body**:

```json
{
  "old_password": "oldpass123",
  "new_password": "newpass456"
}
```

**Response** (HTTP 200):

```json
{
  "detail": "Password updated"
}
```

---

## WebSocket API

### Connection

```javascript
const ws = new WebSocket(`ws://localhost:8000/api/ws/?token=sk_live_abc123...`);

ws.onopen = () => {
  console.log("Connected to RenderHive");
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("Received:", message.type, message);
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = () => {
  console.log("Disconnected from RenderHive");
};
```

### Message Types

#### `job_state_changed`

```json
{
  "type": "job_state_changed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "new_state": "RUNNING",
  "timestamp": "2025-01-15T10:30:45Z"
}
```

#### `task_state_changed`

```json
{
  "type": "task_state_changed",
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "new_state": "SUCCEEDED",
  "completed_at": "2025-01-15T10:45:12Z",
  "exit_code": 0,
  "duration_seconds": 423
}
```

#### `worker_telemetry_update`

```json
{
  "type": "worker_telemetry_update",
  "worker_id": "550e8400-e29b-41d4-a716-446655440002",
  "cpu_usage_percent": 67.3,
  "memory_usage_gb": 14.2,
  "memory_total_gb": 32.0,
  "gpu_usage_percent": [89.5, 45.2],
  "timestamp": "2025-01-15T10:30:45Z"
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "detail": "Authentication credentials were not provided.",
  "code": "not_authenticated"
}
```

### Common HTTP Status Codes

| Code | Meaning      | Example               |
| ---- | ------------ | --------------------- |
| 200  | OK           | GET successful        |
| 201  | Created      | POST job created      |
| 204  | No Content   | DELETE successful     |
| 400  | Bad Request  | Invalid payload       |
| 401  | Unauthorized | Missing token         |
| 403  | Forbidden    | Not allowed to access |
| 404  | Not Found    | Job doesn't exist     |
| 409  | Conflict     | Duplicate job name    |
| 500  | Server Error | Backend crash         |

---

## Rate Limiting

Currently not implemented, but planned for production:

- 1000 requests/minute per IP
- 100 job submissions/hour per user
- 50 concurrent WebSocket connections per IP

---

## API Versioning

Current API version: **v1** (default)

Future versions:

- `/api/v2/` — Planned for Q2 2025
- `/api/v1/` — Maintained for 2 years after v2 release

---

## SDK Examples

### Python

```python
import requests

API_URL = "http://localhost:8000"
API_TOKEN = "sk_live_abc123..."

headers = {"Authorization": f"Bearer {API_TOKEN}"}

# List jobs
response = requests.get(
    f"{API_URL}/api/jobs/?state=RUNNING",
    headers=headers
)
jobs = response.json()

# Create job
job_payload = {
    "name": "test_job_001",
    "visible_name": "Test Job",
    "project": "TestProject",
    "layers": [...]
}
response = requests.post(
    f"{API_URL}/api/jobs/",
    json=job_payload,
    headers=headers
)
job = response.json()

# Get job details
response = requests.get(
    f"{API_URL}/api/jobs/{job['id']}/",
    headers=headers
)
job_detail = response.json()
```

### JavaScript/TypeScript

```typescript
const API_URL = "http://localhost:8000";
const API_TOKEN = "sk_live_abc123...";

async function listJobs(state?: string) {
  const params = new URLSearchParams();
  if (state) params.append("state", state);

  const response = await fetch(`${API_URL}/api/jobs/?${params}`, {
    headers: {
      Authorization: `Bearer ${API_TOKEN}`,
    },
  });

  return response.json();
}

async function submitJob(jobPayload: any) {
  const response = await fetch(`${API_URL}/api/jobs/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(jobPayload),
  });

  return response.json();
}

// WebSocket
const ws = new WebSocket(`ws://localhost:8000/api/ws/?token=${API_TOKEN}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === "job_state_changed") {
    console.log(`Job ${message.job_id} is now ${message.new_state}`);
  }
};
```

---

## OpenAPI Documentation

Full API documentation available at:

- **Swagger UI**: http://localhost:8000/api/schema/swagger/
- **ReDoc**: http://localhost:8000/api/schema/redoc/
- **OpenAPI JSON**: http://localhost:8000/api/schema/

Download spec:

```bash
curl http://localhost:8000/api/schema/ > renderhive-openapi.json
```

---

This API reference covers all production-ready endpoints. For more examples and use cases, see the frontend and plugin source code.
