# Architecture Deep Dive

## System Components

### 1. Frontend (Next.js + React)

**Location**: `frontend/`

**Technology Stack**:

- Next.js 16 (App Router)
- React 19 with server components
- TypeScript (strict mode)
- Tailwind CSS v4
- Shadcn UI component library
- API layer with axios/fetch

**Key Routes**:

- `/` — Dashboard home
- `/jobs` — Job queue and monitoring
- `/jobs/[id]` — Job details, tasks, logs
- `/workers` — Worker pool status
- `/nodes` — Individual worker details
- `/settings` — User preferences, API tokens
- `/logs` — Centralized log viewer

**State Management**:

- React Query for server-state (API caching)
- Context API for UI state
- URL-based pagination and filtering

**Real-Time Updates**:

- WebSocket connection to `/api/ws/` for live job updates
- Fallback to polling (5s interval) if WebSocket unavailable
- Redux-style event dispatching for dashboard refresh

**API Integration**:

```typescript
// src/services/api.ts
export const api = {
  jobs: {
    list: () => GET /api/jobs/,
    get: (id) => GET /api/jobs/{id}/,
    create: (payload) => POST /api/jobs/,
    update: (id, payload) => PATCH /api/jobs/{id}/,
    pause: (id) => POST /api/jobs/{id}/pause/,
    resume: (id) => POST /api/jobs/{id}/resume/,
    retryFailed: (id) => POST /api/jobs/{id}/retry_failed_tasks/,
  },
  workers: { ... },
  tasks: { ... },
  auth: { ... }
}
```

---

### 2. Backend API (Django REST Framework)

**Location**: `backend/`

**Technology Stack**:

- Django 5.2
- Django REST Framework (DRF)
- drf-spectacular (OpenAPI schema generation)
- django-allauth (authentication)
- Django Signals for event dispatching
- PostgreSQL ORM

**Core Applications**:

#### `apps/jobs/`

Manages Job, Layer, Task entities and their state machines.

**Models**:

- `Job` — Top-level render submission (UUID, name, project, user, state, counters)
- `Layer` — Render pass/utility layer within a job (name, type: RENDER/UTIL/POST)
- `Task` — Atomic render unit (frame or sequence segment, frame_range, retry_count)
- `Dependency` — Explicit task/layer/job ordering (type: JOB_ON_JOB, LAYER_ON_LAYER, TASK_ON_TASK)

**State Machines**:

Job States:

```
PENDING → RUNNING → FINISHED
       ↘ (on first layer failure) ↗ FAILED
       ↓ (operator pause)
       PAUSED → (operator resume) → RUNNING
```

Task States:

```
WAITING → READY → RUNNING → SUCCEEDED
       ↓         ↓ (retry)  ↓
       ↓    (READY - loop)  FAILED
       ↑─────────────────────↑
       Unblocked by dependency
```

**API Endpoints**:

```
POST   /api/jobs/                      # Create job
GET    /api/jobs/                      # List (paginated)
GET    /api/jobs/{id}/                 # Retrieve
PATCH  /api/jobs/{id}/                 # Update
POST   /api/jobs/{id}/pause/           # Pause execution
POST   /api/jobs/{id}/resume/          # Resume
POST   /api/jobs/{id}/retry_failed_tasks/  # Requeue failures
DELETE /api/jobs/{id}/                 # Hard delete (if PENDING)

GET    /api/jobs/{id}/layers/          # Get layers
POST   /api/jobs/{id}/layers/          # Create layer
GET    /api/layers/{id}/tasks/         # Get tasks in layer
```

**Signals** (`signals.py`):

- `pre_save`: Validate state transitions, check dependencies
- `post_save`: Update counter caches, trigger Celery dispatch task
- `post_delete`: Cleanup logs, unblock dependent jobs

#### `apps/workers/`

Manages Worker and WorkerPool entities.

**Models**:

- `WorkerPool` — Logical grouping (e.g., "GPU_NODES", "CPU_ONLY", "STUDIO_A")
- `Worker` — Individual render node (name, pool, state, telemetry)

**Telemetry**:

```python
{
    "cpu_usage_percent": 45.2,
    "memory_usage_gb": 8.5,
    "memory_total_gb": 32.0,
    "gpu_count": 2,
    "gpu_memory_gb": [12.0, 12.0],
    "gpu_usage_percent": [75.0, 50.0],
    "network_latency_ms": 2.5,
    "last_heartbeat": "2025-01-15T10:30:45Z",
}
```

**API Endpoints**:

```
GET    /api/workers/                   # List all workers
GET    /api/workers/{id}/              # Retrieve
PATCH  /api/workers/{id}/              # Update capabilities
POST   /api/workers/heartbeat/         # Worker health check + metrics
POST   /api/workers/{id}/shutdown/     # Graceful offline

GET    /api/pools/                     # List pools
POST   /api/pools/                     # Create pool
```

#### `apps/users/`

Handles user authentication, profiles, and permissions.

**Models**:

- `User` — Django built-in (username, email, groups)
- `UserProfile` — Extended metadata (department, api_token, preferences)

**Permission System**:

- Global: Superuser (all operations)
- Department-scoped: Can only view jobs submitted by same department
- Task-level: Can only edit/delete own submitted jobs

**API Endpoints**:

```
GET    /api/users/me/                  # Current user profile
POST   /api/users/me/change-password/  # Update password
POST   /api/auth/login/                # Browser session login
POST   /api/auth/logout/               # Destroy session
POST   /api/auth/refresh-token/        # Get new API token
GET    /api/auth/google/callback/      # OAuth2 Google
```

---

### 3. Message Queue & Scheduling (Celery)

**Configuration**: `backend/config/celery.py`

**Broker**: Redis (localhost:6379)  
**Result Backend**: Redis  
**Beat Scheduler**: Included (persistence via database)

**Core Tasks**:

#### `dispatch_ready_tasks()`

Runs every **tick** (hardcoded 1 second interval in worker):

```
1. Query all READY tasks (dependencies resolved)
2. For each READY task:
   → Calculate deterministic score (priority, resource fit, frame order)
   → If multiple tasks within 5% of top score: call AI tie-breaker
   → Get AI rank if available
3. Sort by (AI rank, deterministic score) descending
4. For each sorted task:
   → Claim (atomic DB transaction)
   → Assign to least-busy worker matching pool/requirements
   → Change state to RUNNING
```

#### `collect_worker_telemetry()`

Scheduled every **60 seconds** via Celery Beat:

```
1. Aggregate telemetry from all workers
2. Calculate farm-wide metrics:
   - Total CPU cores utilized / available
   - Total GPU VRAM utilized / available
   - Memory usage percentage
   - Network latency percentiles
3. Store in Redis cache (TTL 300s)
4. Emit to WebSocket subscribers
```

#### `reap_stale_workers()`

Scheduled every **15 seconds**:

```
1. Check each worker's last_heartbeat timestamp
2. If now - last_heartbeat > 30 seconds:
   → Worker state = OFFLINE
   → Requeue all RUNNING tasks from that worker to READY
   → Emit WebSocket event
```

**Custom Task**: `process_task_result(task_id, exit_code, logs)`
Called by worker when task completes:

```
1. Retrieve task record
2. If exit_code == 0:
   → task.state = SUCCEEDED
   → task.completed_at = now
3. Else (non-zero exit code):
   → If task.retries < max_retries:
      ├─ Increment retry_count
      └─ task.state = READY (re-enter queue)
   → Else:
      └─ task.state = FAILED
4. Update job counter caches
5. Check if job is complete:
   → If all tasks SUCCEEDED/SKIPPED: job.state = FINISHED
   → If any task FAILED: job.state = FAILED
6. Emit WebSocket events for dashboard refresh
```

---

### 4. AI Scheduler Service (FastAPI)

**Location**: `backend/ai_scheduler/` (if implemented separately)  
**Alternative**: Inline in Celery task

**Endpoint**: `http://localhost:8001/rank-tasks/` (POST)

**Request Payload**:

```json
{
  "tasks": [
    {
      "task_id": "uuid-1",
      "priority": 75,
      "frame_start": 1,
      "frame_end": 100,
      "deterministic_score": 0.92,
      "worker_pool_include": ["GPU"],
      "worker_pool_exclude": []
    },
    { ... more tasks ... }
  ],
  "available_workers": [
    {
      "worker_id": "uuid-w1",
      "cpu_cores": 16,
      "gpu_count": 2,
      "gpu_vram_gb": 24.0,
      "available_memory_gb": 16.0,
      "pool": "GPU"
    },
    { ... more workers ... }
  ],
  "model_config": {
    "model_type": "llama-cpp",
    "model_path": "/models/tinyllama.gguf",
    "n_threads": 4
  }
}
```

**Response**:

```json
{
  "ranked_tasks": [
    { "task_id": "uuid-1", "ai_rank": 1, "confidence": 0.87 },
    { "task_id": "uuid-3", "ai_rank": 2, "confidence": 0.84 },
    { "task_id": "uuid-2", "ai_rank": 3, "confidence": 0.79 }
  ],
  "inference_ms": 42,
  "model_loaded": true
}
```

**Model Logic**:

- Only ranks when deterministic scores are close (within ±5%)
- Factors in worker capability vs. task requirement
- Outputs confidence score for each ranking
- Falls back gracefully if model loading fails

**Backend Integration**:

```python
# In dispatch_ready_tasks Celery task
try:
    if close_scores_detected:  # Multiple tasks within 5%
        ai_response = requests.post(
            "http://localhost:8001/rank-tasks/",
            json={"tasks": [...], "available_workers": [...]},
            timeout=5
        )
        ai_ranks = {t['task_id']: t['ai_rank'] for t in ai_response['ranked_tasks']}
        # Use ai_ranks as primary sort, deterministic_score as tiebreaker
except (RequestException, Timeout):
    # Fallback to deterministic scoring
    pass
```

---

### 5. Worker Application (Desktop)

**Location**: `worker/`

**Technology**:

- Python 3.11+
- PySide6 (Qt binding)
- Requests library for HTTP
- psutil for system metrics

**Architecture**:

```
WorkerApplication (main.py)
├─ WorkerUI (PySide6 QMainWindow)
│  ├─ StatusPanel (connection, worker_id, pool assignment)
│  ├─ TaskPanel (current task, progress, logs)
│  ├─ MetricsPanel (CPU, RAM, GPU graphs)
│  └─ SettingsPanel (API endpoint, auth, DCC paths)
│
├─ WorkerHeartbeat (threading.Thread)
│  └─ Runs every 5 seconds:
│     ├─ Collect telemetry (CPU, RAM, GPU)
│     ├─ POST /api/workers/heartbeat/
│     └─ Update UI
│
├─ TaskExecutor (threading.Thread)
│  └─ Main loop:
│     ├─ GET /api/workers/{id}/next-task/
│     ├─ Download task metadata
│     ├─ Execute render command (subprocess)
│     ├─ Stream logs back to server
│     ├─ Report result (exit code, metrics)
│     └─ Mark COMPLETED or FAILED
│
└─ DCCIntegration
   ├─ MayaClient (subprocess, MEL/Python API)
   ├─ HoudiniClient (subprocess, Python API)
   └─ BlenderClient (subprocess, Python API)
```

**Worker Lifecycle**:

```
1. STARTUP
   → Initialize PySide6 app
   → Load config (api_url, auth_token, worker_id)
   → Start heartbeat thread
   → Display UI

2. REGISTRATION
   → POST /api/workers/register/ with capabilities
   → Receive worker UUID and assigned pool
   → Store locally

3. POLLING
   → Every 5s heartbeat: POST /api/workers/{id}/heartbeat/
   → Server responds with task if available
   → If task available:
      ├─ Download task details
      └─ Start execution thread
   → No task: sleep 5s, retry

4. TASK EXECUTION
   → Spawn subprocess for render (Maya, Houdini, etc.)
   → Pipe stdout/stderr to log files
   → Monitor process
   → On completion:
      ├─ Capture exit code
      ├─ Collect final metrics
      ├─ POST /api/tasks/{id}/complete/ with results
      └─ Return to polling

5. SHUTDOWN
   → User closes app or receives SIGTERM
   → Gracefully kill current task
   → POST /api/workers/{id}/shutdown/
   → Clean up temp files
   → Exit
```

**Configuration File** (`~/.renderhive/config.json`):

```json
{
  "api_url": "http://localhost:8000",
  "api_token": "sk_live_...",
  "worker_id": "render-node-01",
  "pool": "STUDIO_A",
  "max_concurrent_tasks": 2,
  "dcc_paths": {
    "maya": "C:\\Program Files\\Autodesk\\Maya2024\\bin\\render.exe",
    "houdini": "C:\\Program Files\\Side Effects Software\\Houdini20\\bin\\hrender.exe",
    "blender": "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe"
  },
  "log_directory": "C:\\Users\\artist\\ AppData\\Local\\RenderHive\\logs",
  "temp_directory": "D:\\RenderHive\\temp",
  "telemetry_interval_sec": 5,
  "heartbeat_interval_sec": 5
}
```

---

### 6. Maya Plugin

**Location**: `plugins/maya/`

**Components**:

- `renderhive_maya_submitter.py` — Main plugin entry point
- `ui/` — Qt UI components (job submitter dialog)
- `api/client.py` — HTTP API wrapper
- `validation/` — Scene validation (file paths, render settings)
- `core/` — Core logic (job construction, layer mapping)

**Functionality**:

**Scene Submission**:

```
1. User opens "RenderHive Submitter" menu in Maya
2. Dialog shows:
   - Project name (required)
   - Priority (1-100, default 50)
   - Render layers (checkboxes)
   - Worker pool targeting (include/exclude)
   - Max tasks per worker
   - Frame range override (optional)
3. Click "Validate Scene"
   - Check project path exists
   - Verify render settings
   - Check file paths (textures, caches)
   - Report warnings/errors
4. Click "Submit"
   - Serialize job payload:
     {
       "name": "ProjectName_ShotName_20250115_120000",
       "visible_name": "ProjectName / ShotName",
       "project": "ProjectName",
       "priority": 75,
       "layers": [
         { "name": "beauty", "type": "RENDER", "render_layer": "beauty" },
         { "name": "shadow", "type": "RENDER", "render_layer": "shadow" },
         { "name": "anim_output", "type": "POST", "script_path": "..." }
       ]
     }
   - POST /api/jobs/ with payload
   - Receive job_id
   - Display "Job submitted: {job_id}"
   - Open dashboard in browser
```

**Scene State Recovery**:

```
On plugin startup:
1. Check for saved render state in:
   ~/.renderhive/scene_state.json
2. If job was interrupted:
   - Offer to resume:
     "Previous render interrupted. Resume?"
   - If yes: Show job dashboard, offer to retry failed frames
   - If no: Start fresh
```

**Validation Engine** (`validation/`):

```python
class SceneValidator:
    def validate(scene_path):
        checks = [
            check_project_path(),        # Project root accessible?
            check_render_settings(),     # Resolution, samples, etc.
            check_render_layers(),       # All target layers exist?
            check_file_references(),     # Textures, caches on disk?
            check_mel_scripts(),         # Custom MEL runable?
            check_memory_requirements(), # Estimate vs. worker RAM
            check_plugin_versions(),     # Maya/Arnold/V-Ray version compatibility
        ]
        return {
            "valid": all(c['passed'] for c in checks),
            "warnings": [c for c in checks if c['passed'] == False and c['severity'] == 'warning'],
            "errors": [c for c in checks if c['passed'] == False and c['severity'] == 'error'],
        }
```

**Drag-to-Install**:

- Runs `renderhive_installer.py`
- Detects Maya install path
- Copies plugin to `MAYA_APP_DIR/plug-ins/`
- Registers in `pluginPrefs.mel`
- Restarts Maya plugin system

---

## Data Models & State Machines

### Job State Machine (DetailedView)

```
┌─────────────┐
│   PENDING   │  ← Initial state on submission
└──────┬──────┘
       │ (layers ready, first layer starts)
       ▼
┌─────────────┐
│   RUNNING   │  ← At least one layer actively executing
└──────┬──────┘
       │
    ┌──┴──┐
    ▼     ▼
┌─────────────┐  ┌─────────────┐
│  FINISHED   │  │   FAILED    │  ← Terminal states
└─────────────┘  └─────────────┘
    ▲
    │ (operator action)
    │
┌───┴──────┐
│   PAUSED  │  ← Suspended by user
└─────────┘
```

Counter Caches (updated on task state change):

- `total_tasks` — Immutable after job creation
- `waiting_tasks` — Tasks still blocked by dependencies
- `ready_tasks` — Runnable tasks awaiting worker claim
- `running_tasks` — Currently executing
- `succeeded_tasks` — Completed with exit 0
- `failed_tasks` — Exhausted retries, final failure
- `skipped_tasks` — Manually dismissed failures
- `depend_tasks` — Tasks with unresolved dependencies (subset of WAITING)

Job completion logic:

```
Job is FINISHED when:
  waiting_tasks == 0 AND depend_tasks == 0 AND
  ready_tasks == 0 AND running_tasks == 0 AND
  failed_tasks == 0
  (i.e., ALL tasks are either SUCCEEDED or SKIPPED)

Job is FAILED when:
  Any task reaches FAILED state AND
  (manually paused OR max_retries exceeded)
```

---

### Dependency Resolution

**Graph Topology**:

```
Job A (e.g., render)
  ↓ JOB_ON_JOB
Job B (e.g., composite)
  → Job A must be FINISHED before Job B enters RUNNING

Layer X (beauty)
  ↓ LAYER_ON_LAYER
Layer Y (shadow)
  → Layer X must be fully executed before Layer Y starts

Task 1 (frame 1)
  ↓ TASK_ON_TASK
Task 2 (frame 2)
  → Task 1 must SUCCEED/SKIP before Task 2 becomes READY
```

**Resolution Algorithm** (Topological Sort):

```python
def resolve_dependencies():
    for each WAITING task:
        # Check incoming TASK_ON_TASK dependencies
        blocking_tasks = task.dependencies.filter(
            state__in=['WAITING', 'READY', 'RUNNING']
        )
        if not blocking_tasks:
            # Check incoming LAYER_ON_LAYER
            blocking_layers = task.layer.dependencies.filter(
                state__in=['WAITING', 'READY', 'RUNNING']
            )
            if not blocking_layers:
                # Check incoming JOB_ON_JOB
                blocking_jobs = task.layer.job.dependencies.filter(
                    state__in=['PENDING', 'RUNNING']
                )
                if not blocking_jobs:
                    task.state = READY  # Unblocked!
```

Runs before every dispatch cycle (every 1 second).

---

## Data Flow Diagram

```
┌──────────────────┐
│  Artist in Maya  │
│   (DCC Plugin)   │
└────────┬─────────┘
         │
         │ Job Submission Payload
         ▼
┌──────────────────────────────────────┐
│  Django REST API (/api/jobs/)        │
│  - Validate payload                  │
│  - Create Job, Layer, Task records   │
│  - Enqueue signal handlers           │
└────────┬─────────────────────────────┘
         │
         │ post_save signal
         ▼
┌──────────────────────────────────────┐
│  Backend Signal Handlers             │
│  - Validate state transitions        │
│  - Check dependency DAG              │
│  - Schedule dispatch task            │
└────────┬─────────────────────────────┘
         │
         │ Celery Task: dispatch_ready_tasks
         ▼
┌──────────────────────────────────────┐
│  Celery Worker                       │
│  1. Resolve dependencies             │
│  2. Calculate deterministic scores   │
│  3. Query AI tie-breaker (optional)  │
│  4. Sort tasks by rank               │
│  5. Claim highest-rank task          │
│  6. Assign to optimal worker         │
│  7. Update task.state = RUNNING      │
└────────┬─────────────────────────────┘
         │
         │ Task assignment
         ▼
┌──────────────────────────────────────┐
│  Worker (Render Node)                │
│  1. Poll /api/workers/{id}/tasks/    │
│  2. Download task metadata           │
│  3. Execute render command           │
│  4. Capture stdout/stderr            │
│  5. Monitor process                  │
│  6. POST /api/tasks/{id}/complete/   │
└────────┬─────────────────────────────┘
         │
         │ Task completion
         ▼
┌──────────────────────────────────────┐
│  Celery Task: process_task_result    │
│  1. Evaluate exit code               │
│  2. Update task.state (SUCCESS/FAIL) │
│  3. Increment job counters           │
│  4. Check job completion criteria    │
│  5. Update job.state if needed       │
│  6. Emit WebSocket events            │
└────────┬─────────────────────────────┘
         │
         │ Real-time update
         ▼
┌──────────────────────────────────────┐
│  Dashboard (Next.js)                 │
│  - Display job progress              │
│  - Show task breakdown               │
│  - Stream logs                       │
│  - Render outputs                    │
└──────────────────────────────────────┘
```

---

## Database Schema Summary

```sql
-- Jobs table (approximately)
CREATE TABLE jobs_job (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    visible_name VARCHAR(255),
    project VARCHAR(64) NOT NULL,
    department VARCHAR(64),
    user VARCHAR(64) NOT NULL,
    submitted_by_id INTEGER FOREIGN KEY,
    state VARCHAR(16),
    is_paused BOOLEAN,
    priority INTEGER,
    max_tasks_per_worker INTEGER,
    log_directory VARCHAR(2048),
    -- Counter caches
    total_tasks INTEGER DEFAULT 0,
    waiting_tasks INTEGER DEFAULT 0,
    ready_tasks INTEGER DEFAULT 0,
    running_tasks INTEGER DEFAULT 0,
    succeeded_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    skipped_tasks INTEGER DEFAULT 0,
    depend_tasks INTEGER DEFAULT 0,
    -- Timestamps
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    stopped_at TIMESTAMP NULL,
    -- Indexes
    INDEX idx_project,
    INDEX idx_state,
    INDEX idx_priority
);

-- Layers table
CREATE TABLE jobs_layer (
    id UUID PRIMARY KEY,
    job_id UUID FOREIGN KEY NOT NULL,
    name VARCHAR(255),
    type VARCHAR(16),  -- RENDER, UTIL, POST
    order INTEGER,
    state VARCHAR(16),  -- WAITING, READY, RUNNING, FINISHED, FAILED
    created_at TIMESTAMP,
    INDEX idx_job_id,
    INDEX idx_state
);

-- Tasks table
CREATE TABLE jobs_task (
    id UUID PRIMARY KEY,
    layer_id UUID FOREIGN KEY NOT NULL,
    frame_start INTEGER,
    frame_end INTEGER,
    state VARCHAR(16),  -- WAITING, READY, RUNNING, SUCCEEDED, FAILED, SKIPPED
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER,
    worker_id UUID FOREIGN KEY NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    exit_code INTEGER NULL,
    output_path VARCHAR(2048),
    -- Indexes
    INDEX idx_layer_id,
    INDEX idx_state,
    INDEX idx_worker_id
);

-- Dependencies table
CREATE TABLE jobs_dependency (
    id UUID PRIMARY KEY,
    type VARCHAR(16),  -- JOB_ON_JOB, LAYER_ON_LAYER, TASK_ON_TASK
    upstream_id UUID FOREIGN KEY,   -- Job/Layer/Task that must complete first
    downstream_id UUID FOREIGN KEY, -- Job/Layer/Task that must wait
    created_at TIMESTAMP,
    INDEX idx_upstream_id,
    INDEX idx_downstream_id
);

-- Workers table
CREATE TABLE workers_worker (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE,
    pool_id UUID FOREIGN KEY,
    state VARCHAR(16),  -- ONLINE, OFFLINE, DISABLED
    capabilities_json JSON,  -- { "cpu_cores": 16, "gpu_count": 2, ... }
    telemetry_json JSON,     -- { "cpu_usage_percent": 45.2, ... }
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    -- Indexes
    INDEX idx_pool_id,
    INDEX idx_state,
    INDEX idx_last_heartbeat
);

-- Worker pools table
CREATE TABLE workers_workerpool (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE,
    description TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Job ↔ Pool M2M relations
CREATE TABLE jobs_job_included_pools (
    job_id UUID FOREIGN KEY,
    workerpool_id UUID FOREIGN KEY,
    PRIMARY KEY (job_id, workerpool_id)
);

CREATE TABLE jobs_job_excluded_pools (
    job_id UUID FOREIGN KEY,
    workerpool_id UUID FOREIGN KEY,
    PRIMARY KEY (job_id, workerpool_id)
);
```

---

## WebSocket Real-Time Updates

**Endpoint**: `ws://localhost:8000/api/ws/`

**Authentication**: Bearer token in query string

```
ws://localhost:8000/api/ws/?token=sk_live_...
```

**Message Types** (JSON):

```json
{
  "type": "job_state_changed",
  "job_id": "uuid",
  "new_state": "RUNNING",
  "timestamp": "2025-01-15T10:30:45Z"
}
```

```json
{
  "type": "task_state_changed",
  "task_id": "uuid",
  "new_state": "SUCCEEDED",
  "completed_at": "2025-01-15T10:45:12Z",
  "exit_code": 0
}
```

```json
{
  "type": "worker_telemetry_update",
  "worker_id": "uuid",
  "cpu_usage_percent": 67.3,
  "memory_usage_gb": 14.2,
  "gpu_usage_percent": [89.5, 45.2]
}
```

**Consumer** (Frontend):

```typescript
// src/services/websocket.ts
export class JobWebSocketClient {
  connect(token: string) {
    this.ws = new WebSocket(`ws://localhost:8000/api/ws/?token=${token}`);
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      switch (msg.type) {
        case "job_state_changed":
          dispatch(updateJobState(msg.job_id, msg.new_state));
          break;
        case "task_state_changed":
          dispatch(updateTaskState(msg.task_id, msg.new_state));
          break;
        // ... handle other types
      }
    };
  }
}
```

---

This architecture provides **scalability**, **fault tolerance**, and **extensibility** for modern rendering workflows.
