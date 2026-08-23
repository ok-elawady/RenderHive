# Backend API Development Guide

## Directory Structure

```
backend/
├── config/                    # Django project settings
│   ├── settings/
│   │   ├── base.py           # Common settings
│   │   ├── development.py    # DEV overrides
│   │   └── production.py     # PROD overrides
│   ├── urls.py               # URL routing
│   ├── wsgi.py               # WSGI app
│   ├── asgi.py               # ASGI app (WebSocket)
│   └── celery.py             # Celery task queue config
├── apps/
│   ├── jobs/                 # Job orchestration
│   │   ├── models.py         # Job, Layer, Task, Dependency
│   │   ├── serializers.py    # DRF serializers (validation, response format)
│   │   ├── views.py          # ViewSets for CRUD operations
│   │   ├── urls.py           # URL patterns
│   │   ├── services.py       # Business logic (dispatch, scoring)
│   │   ├── signals.py        # Django signals (state transitions)
│   │   ├── permissions.py    # Custom permission classes
│   │   ├── tasks.py          # Celery tasks (async jobs)
│   │   ├── migrations/       # Database migrations
│   │   └── tests/            # Unit & integration tests
│   ├── workers/              # Worker pool management
│   │   ├── models.py         # Worker, WorkerPool
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tasks.py          # Telemetry collection, worker reaping
│   └── users/                # User authentication & profiles
│       ├── models.py         # User, UserProfile
│       ├── adapters.py       # django-allauth customization
│       └── tests/
├── manage.py                 # Django CLI
├── pyproject.toml           # Python dependencies
└── pytest.ini               # pytest configuration
```

---

## Core Models

### Job Model

**Location**: `apps/jobs/models.py`

```python
class Job(models.Model):
    """Top-level render submission."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(max_length=255, unique=True, db_index=True)
    visible_name = CharField(max_length=255, blank=True)

    project = CharField(max_length=64, db_index=True)
    department = CharField(max_length=64, blank=True)

    user = CharField(max_length=64)  # OS username from DCC plugin
    submitted_by = ForeignKey(User, on_delete=SET_NULL, null=True)

    state = CharField(
        max_length=16,
        choices=JobState.choices,
        default=JobState.PENDING,
        db_index=True
    )
    is_paused = BooleanField(default=False)
    priority = IntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    max_tasks_per_worker = PositiveIntegerField(default=1)
    log_directory = CharField(max_length=2048)

    # Counter caches (updated on every task state change)
    total_tasks = IntegerField(default=0)
    waiting_tasks = IntegerField(default=0)
    ready_tasks = IntegerField(default=0)
    running_tasks = IntegerField(default=0)
    succeeded_tasks = IntegerField(default=0)
    failed_tasks = IntegerField(default=0)
    skipped_tasks = IntegerField(default=0)
    depend_tasks = IntegerField(default=0)

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    stopped_at = DateTimeField(null=True, blank=True)

    included_pools = ManyToManyField(
        'workers.WorkerPool',
        blank=True,
        related_name='included_jobs',
        help_text="If specified, only workers in these pools can process this job"
    )
    excluded_pools = ManyToManyField(
        'workers.WorkerPool',
        blank=True,
        related_name='excluded_jobs'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['project', 'state']),
            Index(fields=['user', 'state']),
            Index(fields=['-priority', 'state']),
        ]
```

**Key Invariants**:

- `total_tasks` is immutable after job creation
- Counter sum: `waiting + ready + running + succeeded + failed + skipped == total_tasks`
- Job reaches `FINISHED` only when: `failed_tasks == 0` (or manually skipped)
- Job reaches `FAILED` when: first task exceeds max_retries
- Only `PENDING` jobs can be deleted

---

### Layer Model

```python
class Layer(models.Model):
    """A render pass or utility pass within a job."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    job = ForeignKey(Job, on_delete=CASCADE, related_name='layers')

    name = CharField(max_length=255)  # e.g., "beauty", "shadow"
    type = CharField(
        max_length=16,
        choices=LayerType.choices,  # RENDER, UTIL, POST
        default=LayerType.RENDER
    )
    order = IntegerField(db_index=True)  # Execution order

    # Render layer metadata (if type=RENDER)
    render_layer_name = CharField(max_length=255, blank=True, null=True)

    # Utility script (if type=UTIL or POST)
    script_path = CharField(max_length=2048, blank=True, null=True)

    state = CharField(
        max_length=16,
        choices=LayerState.choices,
        default=LayerState.WAITING
    )

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

---

### Task Model

```python
class Task(models.Model):
    """An atomic render unit (frame or sequence segment)."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)
    layer = ForeignKey(Layer, on_delete=CASCADE, related_name='tasks')

    frame_start = IntegerField()
    frame_end = IntegerField()  # Inclusive

    state = CharField(
        max_length=16,
        choices=TaskState.choices,
        default=TaskState.WAITING,
        db_index=True
    )

    retry_count = IntegerField(default=0)
    max_retries = IntegerField(default=3)

    worker = ForeignKey(
        'workers.Worker',
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )

    started_at = DateTimeField(null=True, blank=True)
    completed_at = DateTimeField(null=True, blank=True)
    exit_code = IntegerField(null=True, blank=True)

    output_path = CharField(max_length=2048, blank=True, null=True)
    log_url = URLField(blank=True, null=True)  # Path to task logs

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        ordering = ['layer', 'frame_start']
        indexes = [
            Index(fields=['layer', 'state']),
            Index(fields=['worker', 'state']),
            Index(fields=['state', 'retry_count']),
        ]
```

**Task Lifecycle**:

```
WAITING (blocked by dependencies)
  ↓ (all dependencies met)
READY (eligible for dispatch)
  ↓ (claimed by worker)
RUNNING (actively executing)
  ├─ (exit_code == 0)
  │  ↓
  │  SUCCEEDED (terminal)
  │
  └─ (exit_code != 0)
     ├─ (retry_count < max_retries)
     │  ↓
     │  READY (retry, back to dispatch)
     │
     └─ (retry_count >= max_retries)
        ├─ (manually skipped by admin)
        │  ↓
        │  SKIPPED (terminal, but doesn't block job)
        │
        └─ (not skipped)
           ↓
           FAILED (terminal, blocks job)
```

---

### Dependency Model

```python
class Dependency(models.Model):
    """Explicit ordering constraint."""

    id = UUIDField(primary_key=True, default=uuid.uuid4)

    type = CharField(
        max_length=16,
        choices=DependencyType.choices,  # JOB_ON_JOB, LAYER_ON_LAYER, TASK_ON_TASK
        db_index=True
    )

    # For JOB_ON_JOB: upstream_id and downstream_id are Job UUIDs
    # For LAYER_ON_LAYER: Layer UUIDs
    # For TASK_ON_TASK: Task UUIDs

    upstream_id = UUIDField(db_index=True)
    downstream_id = UUIDField(db_index=True)

    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('type', 'upstream_id', 'downstream_id')
        indexes = [
            Index(fields=['upstream_id', 'type']),
            Index(fields=['downstream_id', 'type']),
        ]
```

**Resolution**:

```
Task.state = WAITING
Check: Does this task have incoming TASK_ON_TASK dependencies?
  ├─ If YES: Check all upstream tasks are SUCCEEDED or SKIPPED
  │    If all succeeded: Check layer dependencies
  │    Else: Stay WAITING
  └─ If NO: Check layer dependencies
       └─ Check incoming LAYER_ON_LAYER deps…
          └─ Check job dependencies
             └─ If all clear: Task.state = READY
```

Runs in `dispatch_ready_tasks()` every 1 second.

---

## API Endpoints

### Jobs API

**Base URL**: `/api/jobs/`

#### List Jobs (Paginated)

```bash
GET /api/jobs/?page=1&limit=20&search=query&state=RUNNING&ordering=-priority

# Response (HTTP 200)
{
  "count": 156,
  "next": "http://localhost:8000/api/jobs/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "ProjectName_ShotName_20250115_120000",
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
      "ready_tasks": 5,
      "running_tasks": 2,
      "succeeded_tasks": 93,
      "failed_tasks": 0,
      "skipped_tasks": 0,
      "depend_tasks": 0,
      "created_at": "2025-01-15T09:00:00Z",
      "updated_at": "2025-01-15T10:30:45Z",
      "stopped_at": null,
      "included_pools": ["STUDIO_A"],
      "excluded_pools": []
    }
  ]
}
```

**Query Parameters**:

- `page` — Page number (default 1)
- `limit` — Results per page (default 20, max 100)
- `search` — Search by name or visible_name
- `state` — Filter by state (PENDING, RUNNING, FINISHED, FAILED)
- `project` — Filter by project
- `department` — Filter by department
- `user` — Filter by submitter
- `priority` — Filter by priority (min-max range)
- `ordering` — Sort field: `created_at`, `-priority`, `state`, etc.

---

#### Create Job

```bash
POST /api/jobs/

{
  "name": "unique-job-identifier",
  "visible_name": "ProjectName / ShotName",
  "project": "ProjectName",
  "department": "Lighting",
  "user": "john.doe",
  "priority": 75,
  "max_tasks_per_worker": 1,
  "log_directory": "/storage/renderhive/logs/job-id",
  "layers": [
    {
      "name": "beauty",
      "type": "RENDER",
      "order": 1,
      "render_layer_name": "beauty",
      "tasks": [
        {"frame_start": 1, "frame_end": 10, "max_retries": 3},
        {"frame_start": 11, "frame_end": 20, "max_retries": 3}
      ]
    },
    {
      "name": "composite",
      "type": "POST",
      "order": 2,
      "script_path": "/projects/ProjectName/scripts/composite.py",
      "tasks": [
        {"frame_start": 1, "frame_end": 20, "max_retries": 2}
      ]
    }
  ],
  "dependencies": [
    {
      "type": "LAYER_ON_LAYER",
      "upstream_id": "layer-beauty-uuid",
      "downstream_id": "layer-composite-uuid"
    }
  ],
  "included_pools": ["STUDIO_A"],
  "excluded_pools": []
}

# Response (HTTP 201)
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "unique-job-identifier",
  "state": "PENDING",
  # ... (rest of job fields)
}
```

**Validation Rules**:

- `name` must be unique
- `priority` must be 1-100
- At least one layer required
- Each layer must have at least one task
- Frame ranges must be positive integers
- max_retries must be >= 0

---

#### Retrieve Job

```bash
GET /api/jobs/{id}/

# Response (HTTP 200)
# Same schema as list
```

---

#### Update Job

```bash
PATCH /api/jobs/{id}/

{
  "visible_name": "New Name",
  "priority": 50,
  "is_paused": true
}

# Response (HTTP 200)
# Updated job object
```

**Updatable Fields**:

- `visible_name`
- `priority`
- `is_paused`

**Immutable Fields**:

- `name`, `project`, `state`, `layers` (use specific endpoints)

---

#### Pause Job

```bash
POST /api/jobs/{id}/pause/

# Response (HTTP 200)
{ "state": "PAUSED" }
```

Effect:

- Job.is_paused = True
- New tasks NOT dispatched to workers
- Running tasks continue to completion

---

#### Resume Job

```bash
POST /api/jobs/{id}/resume/

# Response (HTTP 200)
{ "state": "RUNNING" }
```

Effect:

- Job.is_paused = False
- READY tasks re-enter dispatch queue

---

#### Retry Failed Tasks

```bash
POST /api/jobs/{id}/retry_failed_tasks/

{
  "max_retries": 2  # Optional, override task's max_retries
}

# Response (HTTP 200)
{
  "retried_count": 3,
  "tasks": [
    { "id": "task-uuid-1", "state": "READY" },
    { "id": "task-uuid-2", "state": "READY" }
  ]
}
```

Effect:

- All FAILED tasks: state → READY
- retry_count reset to 0
- max_retries updated if provided
- Job state → RUNNING

---

#### Delete Job

```bash
DELETE /api/jobs/{id}/

# Response (HTTP 204 No Content)
```

**Constraints**:

- Only allowed if job.state == PENDING
- Deletes all associated layers, tasks, logs

---

### Workers API

**Base URL**: `/api/workers/`

#### List Workers

```bash
GET /api/workers/?pool=STUDIO_A&state=ONLINE

# Response (HTTP 200)
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

#### Worker Heartbeat (Health Check + Telemetry)

```bash
POST /api/workers/heartbeat/

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

# Response (HTTP 200)
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
  } // Or null if no task available
}
```

**Frequency**: Every 5 seconds per worker

**Effect**:

- Updates worker.last_heartbeat
- Updates worker.telemetry
- If no task assigned: checks dispatch queue, claims highest-priority ready task
- Sets task.state = RUNNING, task.worker_id = worker_id

---

#### Task Completion Report

```bash
POST /api/tasks/{task_id}/complete/

{
  "exit_code": 0,
  "duration_seconds": 42.3,
  "log_content": "V-Ray: Frame 1 rendered in 42.3 seconds…"
}

# Response (HTTP 200)
{
  "task_id": "task-uuid",
  "state": "SUCCEEDED",
  "job_id": "job-uuid",
  "job_state": "RUNNING"  // Updated if job finished
}
```

**Effect** (Celery task `process_task_result`):

1. Task.exit_code = 0 → Task.state = SUCCEEDED
2. Increment Job.succeeded_tasks counter
3. Check job completion:
   ```
   if job.running_tasks == 0 and job.ready_tasks == 0:
       if job.failed_tasks == 0:
           job.state = FINISHED
       else:
           job.state = FAILED
   ```
4. Emit WebSocket: `{"type": "task_state_changed", "task_id": ..., "new_state": "SUCCEEDED"}`
5. Emit WebSocket: `{"type": "job_state_changed", "job_id": ..., "new_state": "FINISHED"}`

---

## Serializers (Validation & Response Format)

**Location**: `apps/jobs/serializers.py`

```python
class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'layer_id', 'frame_start', 'frame_end',
            'state', 'retry_count', 'max_retries',
            'worker_id', 'started_at', 'completed_at',
            'exit_code', 'output_path', 'log_url',
            'created_at', 'updated_at'
        ]

    def validate(self, data):
        if data['frame_end'] < data['frame_start']:
            raise serializers.ValidationError(
                "frame_end must be >= frame_start"
            )
        return data

class LayerSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)

    class Meta:
        model = Layer
        fields = [
            'id', 'job_id', 'name', 'type', 'order',
            'render_layer_name', 'script_path', 'state',
            'tasks', 'created_at', 'updated_at'
        ]

class JobSerializer(serializers.ModelSerializer):
    layers = LayerSerializer(many=True, read_only=True)
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'name', 'visible_name', 'project', 'department',
            'user', 'submitted_by', 'state', 'is_paused', 'priority',
            'max_tasks_per_worker', 'log_directory',
            'total_tasks', 'waiting_tasks', 'ready_tasks',
            'running_tasks', 'succeeded_tasks', 'failed_tasks',
            'skipped_tasks', 'depend_tasks',
            'progress_percent', 'layers',
            'included_pools', 'excluded_pools',
            'created_at', 'updated_at', 'stopped_at'
        ]

    def get_progress_percent(self, obj):
        if obj.total_tasks == 0:
            return 0
        return (obj.succeeded_tasks + obj.skipped_tasks) / obj.total_tasks * 100
```

---

## Celery Tasks (Async Operations)

**Location**: `apps/jobs/tasks.py`

### 1. `dispatch_ready_tasks()`

```python
@shared_task(bind=True)
def dispatch_ready_tasks(self):
    """Run every 1 second. Dispatch READY tasks to workers."""

    # 1. Resolve dependencies: WAITING → READY
    resolve_dependencies()

    # 2. Calculate scores
    ready_tasks = Task.objects.filter(
        state=TaskState.READY
    ).select_related('layer__job', 'worker')

    tasks_with_scores = []
    for task in ready_tasks:
        score = calculate_deterministic_score(task)
        tasks_with_scores.append((task, score))

    # 3. Sort and optionally apply AI tie-breaker
    tasks_with_scores.sort(key=lambda x: x[1], reverse=True)

    if should_query_ai(tasks_with_scores):
        ai_results = query_ai_scheduler(tasks_with_scores)
        # Re-sort by AI rank
        tasks_with_scores = apply_ai_ranking(
            tasks_with_scores, ai_results
        )

    # 4. Claim tasks
    for task, score in tasks_with_scores:
        worker = find_optimal_worker(task)
        if worker:
            claim_task_for_worker(task, worker)

def find_optimal_worker(task):
    """Find best worker based on pool inclusion/exclusion and load."""
    job = task.layer.job

    # Filter by pool constraints
    workers = Worker.objects.filter(
        state=WorkerState.ONLINE
    )

    # Include constraint
    if job.included_pools.exists():
        workers = workers.filter(pool__in=job.included_pools.all())

    # Exclude constraint
    if job.excluded_pools.exists():
        workers = workers.exclude(pool__in=job.excluded_pools.all())

    # Select least-busy (minimum running_tasks)
    workers = workers.annotate(
        running_count=Count(
            'tasks',
            filter=Q(tasks__state=TaskState.RUNNING)
        )
    ).order_by('running_count')

    # Respect max_tasks_per_worker
    job_max = job.max_tasks_per_worker
    for worker in workers:
        if worker.running_count < job_max:
            return worker

    return None

def claim_task_for_worker(task, worker):
    """Atomically claim task and change state."""
    with transaction.atomic():
        # Re-fetch with select_for_update (lock)
        task = Task.objects.select_for_update().get(pk=task.id)

        # Double-check state hasn't changed
        if task.state != TaskState.READY:
            return

        task.state = TaskState.RUNNING
        task.worker = worker
        task.started_at = timezone.now()
        task.save()

        # Update job counter
        job = task.layer.job
        job.ready_tasks -= 1
        job.running_tasks += 1
        job.save()
```

### 2. `process_task_result()`

```python
@shared_task(bind=True)
def process_task_result(self, task_id, exit_code, logs):
    """Called by worker when task completes."""

    task = Task.objects.get(pk=task_id)
    job = task.layer.job

    if exit_code == 0:
        task.state = TaskState.SUCCEEDED
        task.exit_code = 0
        job.succeeded_tasks += 1
    else:
        if task.retry_count < task.max_retries:
            # Retry: reset to READY
            task.state = TaskState.READY
            task.retry_count += 1
            task.worker = None
            task.started_at = None
            job.running_tasks -= 1
            job.ready_tasks += 1
        else:
            # Max retries exceeded
            task.state = TaskState.FAILED
            task.exit_code = exit_code
            job.running_tasks -= 1
            job.failed_tasks += 1

    task.completed_at = timezone.now()
    task.save()

    # Check job completion
    if job.running_tasks == 0 and job.ready_tasks == 0:
        if job.failed_tasks == 0:
            job.state = JobState.FINISHED
            job.stopped_at = timezone.now()
        else:
            job.state = JobState.FAILED
            job.stopped_at = timezone.now()

    job.save()

    # Emit WebSocket events
    send_websocket_event({
        'type': 'task_state_changed',
        'task_id': str(task.id),
        'new_state': task.state,
        'completed_at': task.completed_at.isoformat()
    })

    send_websocket_event({
        'type': 'job_state_changed',
        'job_id': str(job.id),
        'new_state': job.state
    })
```

### 3. `collect_worker_telemetry()` (Scheduled via Celery Beat)

```python
@periodic_task(run_every=60)
def collect_worker_telemetry():
    """Aggregate telemetry every 60 seconds."""

    workers = Worker.objects.filter(state=WorkerState.ONLINE)

    total_cpu_cores = sum(w.capabilities['cpu_cores'] for w in workers)
    total_memory_gb = sum(w.capabilities['memory_gb'] for w in workers)
    total_gpu_vram_gb = sum(
        sum(vram_list)
        for w in workers
        for vram_list in [w.capabilities.get('gpu_memory_gb', [])]
    )

    avg_cpu_usage = np.mean([
        w.telemetry.get('cpu_usage_percent', 0)
        for w in workers
    ])

    # Cache in Redis for 5 minutes
    cache.set('farm_metrics', {
        'total_cpu_cores': total_cpu_cores,
        'total_memory_gb': total_memory_gb,
        'total_gpu_vram_gb': total_gpu_vram_gb,
        'avg_cpu_usage_percent': avg_cpu_usage,
        'online_workers': workers.count(),
        'timestamp': timezone.now().isoformat()
    }, timeout=300)
```

### 4. `reap_stale_workers()` (Scheduled via Celery Beat)

```python
@periodic_task(run_every=15)
def reap_stale_workers():
    """Mark offline workers and requeue tasks."""

    stale_threshold = timezone.now() - timedelta(seconds=30)

    stale_workers = Worker.objects.filter(
        state=WorkerState.ONLINE,
        last_heartbeat__lt=stale_threshold
    )

    for worker in stale_workers:
        worker.state = WorkerState.OFFLINE
        worker.save()

        # Requeue all running tasks from this worker
        tasks = Task.objects.filter(
            worker=worker,
            state=TaskState.RUNNING
        )

        for task in tasks:
            task.state = TaskState.READY
            task.worker = None
            task.started_at = None
            task.save()

            # Update job counters
            job = task.layer.job
            job.running_tasks -= 1
            job.ready_tasks += 1
            job.save()

            # Emit WebSocket
            send_websocket_event({
                'type': 'task_reassigned',
                'task_id': str(task.id),
                'worker_id': None,
                'reason': 'worker_stale'
            })
```

---

## Scoring Algorithm

**Deterministic Score Calculation**:

```python
def calculate_deterministic_score(task):
    """
    Score formula:
      score = (priority_weight * job_priority) +
              (resource_fit_weight * resource_fit) +
              (frame_order_weight * frame_order) -
              (retry_penalty * task.retry_count)

    Result: 0.0 to 1.0
    """

    job = task.layer.job

    # Component 1: Job Priority (0.0 to 1.0)
    priority_component = job.priority / 100.0  # 1-100 → 0-1

    # Component 2: Resource Fit (0.0 to 1.0)
    # How well does the task fit available worker resources?
    # (for now, simplified; can be extended per-task requirements)
    resource_fit = 0.5  # Default middle value

    # Component 3: Frame Order (0.0 to 1.0)
    # Lower frame numbers get higher scores (encourage sequential rendering)
    total_frames = task.layer.tasks.count()
    frame_order_component = 1.0 - (task.frame_start / (total_frames * 100))

    # Component 4: Retry Penalty
    # Each retry reduces score by 10%
    retry_penalty = task.retry_count * 0.1

    # Weighted sum
    weights = {
        'priority': 0.6,
        'resource_fit': 0.2,
        'frame_order': 0.1,
        'retry_penalty': 0.1
    }

    score = (
        weights['priority'] * priority_component +
        weights['resource_fit'] * resource_fit +
        weights['frame_order'] * frame_order_component -
        weights['retry_penalty'] * retry_penalty
    )

    return max(0.0, min(1.0, score))  # Clamp 0-1

def should_query_ai(tasks_with_scores):
    """
    Query AI tie-breaker if:
    1. AI enabled
    2. Multiple tasks exist
    3. Top 2 scores within 5% of each other
    """
    if not settings.AI_SCHEDULER_ENABLED or len(tasks_with_scores) < 2:
        return False

    top_score = tasks_with_scores[0][1]
    second_score = tasks_with_scores[1][1]

    delta = abs(top_score - second_score)
    return delta <= 0.05  # Within 5%
```

---

## Signals (State Machine Enforcement)

**Location**: `apps/jobs/signals.py`

```python
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

@receiver(pre_save, sender=Job)
def validate_job_state_transition(sender, instance, **kwargs):
    """Enforce valid state transitions."""

    if instance.pk:  # Existing object
        old = Job.objects.get(pk=instance.pk)
        old_state = old.state
        new_state = instance.state

        # Valid transitions
        valid_transitions = {
            JobState.PENDING: [JobState.RUNNING, JobState.PAUSED],
            JobState.RUNNING: [JobState.FINISHED, JobState.FAILED, JobState.PAUSED],
            JobState.PAUSED: [JobState.RUNNING],
            JobState.FINISHED: [],  # Terminal
            JobState.FAILED: [],    # Terminal
        }

        if new_state not in valid_transitions.get(old_state, []):
            raise ValidationError(
                f"Invalid transition: {old_state} → {new_state}"
            )

@receiver(post_save, sender=Job)
def on_job_state_changed(sender, instance, created, **kwargs):
    """Trigger dispatch when job state changes."""

    if not created and instance.state in [JobState.RUNNING, JobState.PAUSED]:
        if instance.state == JobState.RUNNING:
            # Schedule dispatch task
            dispatch_ready_tasks.apply_async(countdown=1)
```

---

This backend provides a robust, scalable REST API for orchestrating distributed rendering.
