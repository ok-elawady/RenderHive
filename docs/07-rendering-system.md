# Rendering System & Task Execution

## Complete Task Lifecycle

```
┌──────────────────────────────────────────────────────────────┐
│ PHASE 1: SUBMISSION (Artist in Maya)                         │
└──────────────────────────────────────────────────────────────┘

1. Artist opens Maya
   → Runs: `from renderhive_maya_submitter import render_hive_ui`
   → UI loads: Job Submitter Dialog

2. User configures job:
   - Project name: "PixarShort"
   - Shot name: "010_intro"
   - Priority: 75
   - Render layers: [beauty, shadow, anim_output]
   - Frame range: 1-100 (or per-layer)
   - Worker pool: "STUDIO_A" (include), empty (exclude)
   - Max tasks per worker: 1

3. Click "Validate Scene"
   → Validator checks:
      ├─ Project path exists
      ├─ Render settings (resolution, samples, denoise)
      ├─ File references (textures, caches)
      ├─ Maya version vs. Arnold version compatibility
      ├─ Disk space for output
      └─ Memory requirements
   → Report warnings (yellow) and errors (red)

4. Click "Submit"
   → Serializes job payload:
      {
        "name": "PixarShort_010_intro_20250115_120000",
        "visible_name": "PixarShort / 010_intro",
        "project": "PixarShort",
        "priority": 75,
        "layers": [
          {
            "name": "beauty",
            "type": "RENDER",
            "render_layer_name": "beauty",
            "tasks": [
              {"frame_start": 1, "frame_end": 10, "max_retries": 3},
              {"frame_start": 11, "frame_end": 20, "max_retries": 3},
              {"frame_start": 21, "frame_end": 30, "max_retries": 3},
              {"frame_start": 31, "frame_end": 40, "max_retries": 3},
              {"frame_start": 41, "frame_end": 50, "max_retries": 3},
              {"frame_start": 51, "frame_end": 60, "max_retries": 3},
              {"frame_start": 61, "frame_end": 70, "max_retries": 3},
              {"frame_start": 71, "frame_end": 80, "max_retries": 3},
              {"frame_start": 81, "frame_end": 90, "max_retries": 3},
              {"frame_start": 91, "frame_end": 100, "max_retries": 3}
            ]
          },
          {
            "name": "shadow",
            "type": "RENDER",
            "render_layer_name": "shadow",
            "tasks": [...] // 10 tasks for shadow layer
          },
          {
            "name": "anim_output",
            "type": "POST",
            "script_path": "/projects/PixarShort/scripts/post_process.py",
            "tasks": [
              {"frame_start": 1, "frame_end": 100, "max_retries": 2}
            ]
          }
        ],
        "dependencies": [
          {
            "type": "LAYER_ON_LAYER",
            "upstream_id": "beauty-layer-uuid",
            "downstream_id": "anim_output-layer-uuid"
          },
          {
            "type": "LAYER_ON_LAYER",
            "upstream_id": "shadow-layer-uuid",
            "downstream_id": "anim_output-layer-uuid"
          }
        ]
      }
   → POST /api/jobs/ (includes auth token from worker config)
   → Receive: { "id": "job-uuid", "state": "PENDING" }
   → Display: "✓ Job submitted: job-uuid"
   → Open browser: http://dashboard/jobs/job-uuid

┌──────────────────────────────────────────────────────────────┐
│ PHASE 2: INGESTION (Backend API)                             │
└──────────────────────────────────────────────────────────────┘

5. Django REST API receives job:
   → Validate schema (Serializers)
   → Create Job record:
      Job.state = PENDING
      Job.total_tasks = 21 (10+10+1)
      Job.waiting_tasks = 21
   → Create Layer records (x3)
   → Create Task records (x21)
   → Create Dependency records (x2)
   → Save all to PostgreSQL

6. post_save signal fires:
   → Validate state transitions (PENDING is valid initial state)
   → Check job has at least 1 layer and 1 task
   → Schedule dispatch_ready_tasks Celery task (run immediately)

┌──────────────────────────────────────────────────────────────┐
│ PHASE 3: DEPENDENCY RESOLUTION (Celery)                      │
└──────────────────────────────────────────────────────────────┘

7. Celery worker (every 1 second):
   dispatch_ready_tasks() runs:

   For each WAITING task:
   ├─ Check incoming TASK_ON_TASK dependencies
   │  └─ None in this case (per-frame render)
   ├─ Check incoming LAYER_ON_LAYER dependencies
   │  └─ beauty layer has none
   │  └─ shadow layer has none
   │  └─ anim_output depends on beauty AND shadow
   └─ Check incoming JOB_ON_JOB dependencies
      └─ None

   Result:
   ├─ Beauty tasks 1-10: WAITING → READY ✓
   ├─ Shadow tasks 1-10: WAITING → READY ✓
   └─ anim_output tasks: stay WAITING (blocked by beauty/shadow)

   Update Job.ready_tasks = 20
   Update Job.waiting_tasks = 1

┌──────────────────────────────────────────────────────────────┐
│ PHASE 4: TASK SCORING & DISPATCH                             │
└──────────────────────────────────────────────────────────────┘

8. Same Celery cycle, deterministic scoring:
   For each READY task:
   ├─ Priority component: 75 / 100 = 0.75
   ├─ Resource fit: 0.5 (default)
   ├─ Frame order: 1.0 - (frame_start / 1000) ≈ 0.99 for frame 1
   ├─ Retry penalty: 0 (first attempt)
   └─ Score = 0.6*0.75 + 0.2*0.5 + 0.1*0.99 + 0 = 0.749

   Tasks ranked by score (descending):
   ├─ Task beauty 1-10: 0.749
   ├─ Task beauty 11-20: 0.740
   ├─ Task shadow 1-10: 0.749
   ├─ Task shadow 11-20: 0.740
   └─ ... etc

   Check if AI tie-breaker needed:
   ├─ Top score: 0.749
   ├─ Second score: 0.749
   ├─ Delta: 0.000 (< 0.05) → YES, query AI

   If AI enabled:
   └─ POST /ai-scheduler/rank-tasks/
      ├─ Input: Top 10 tasks, available workers
      ├─ LLM prompt: "Which render layer (beauty/shadow) should start first?"
      ├─ LLM output: ["beauty-task-1", "shadow-task-1", "beauty-task-2", ...]
      └─ Re-rank by AI ranking

   If AI unavailable (timeout or error):
   └─ Continue with deterministic score

9. Claim highest-ranked task:
   Task: beauty-frame-1-10
   ├─ Find best worker (online, in STUDIO_A pool, least busy)
   ├─ Worker found: render-node-01 (2/8 cores busy)
   ├─ Atomic DB claim:
   │  task.state = RUNNING
   │  task.worker = render-node-01
   │  task.started_at = now
   ├─ Update job.counters:
   │  job.ready_tasks -= 1 (20 → 19)
   │  job.running_tasks += 1 (0 → 1)
   └─ Task ID: task-1-uuid

10. Repeat for next READY task:
    ├─ Task: shadow-frame-1-10 (tied with beauty, but AI might rank differently)
    ├─ Worker: render-node-02 (2/8 cores busy)
    ├─ Claim for render-node-02
    └─ Update counters

    Now system state:
    ├─ Job.ready_tasks = 18
    ├─ Job.running_tasks = 2
    ├─ Task 1 on render-node-01
    └─ Task 2 on render-node-02

┌──────────────────────────────────────────────────────────────┐
│ PHASE 5: WORKER POLLING & TASK DOWNLOAD                      │
└──────────────────────────────────────────────────────────────┘

11. Worker heartbeat (every 5 seconds):
    Worker: render-node-01
    ├─ Collect telemetry:
    │  ├─ CPU: 45% utilization
    │  ├─ Memory: 14/32 GB
    │  └─ GPU: [8.5/12 GB, 6.2/12 GB]
    ├─ Send heartbeat:
    │  POST /api/workers/heartbeat/
    │  {
    │    "worker_id": "render-node-01",
    │    "telemetry": { "cpu_usage_percent": 45, ... }
    │  }
    └─ Receive response:
       {
         "worker_id": "render-node-01",
         "status": "ok",
         "next_task": {
           "id": "task-1-uuid",
           "layer_id": "beauty-layer-uuid",
           "frame_start": 1,
           "frame_end": 10,
           "render_command": "render.exe -rl beauty -fs 1 -fe 10 -of exr scene.mb",
           "output_path": "/storage/renders/PixarShort/010_intro/beauty/",
           "max_retries": 3
         }
       }

    If already running a task: don't fetch new task (respect max_tasks_per_worker)

┌──────────────────────────────────────────────────────────────┐
│ PHASE 6: RENDER EXECUTION                                    │
└──────────────────────────────────────────────────────────────┘

12. Worker downloads task details & renders:
    render-node-01 TaskExecutor thread:
    ├─ Download full task config & scene file
    ├─ Create temp directory: C:\RenderHive\temp\task-1-uuid\
    ├─ Verify Maya exists: C:\Program Files\Autodesk\Maya2024\bin\render.exe
    ├─ Build render command:
    │  "C:\Program Files\Autodesk\Maya2024\bin\render.exe" \
    │  -rl beauty \
    │  -fs 1 \
    │  -fe 10 \
    │  -x 1920 -y 1080 \
    │  -of exr \
    │  -pad 4 \
    │  -rd /storage/renders/PixarShort/010_intro/beauty/ \
    │  /network/projects/PixarShort/scenes/010_intro.mb
    ├─ Start subprocess:
    │  subprocess.Popen(
    │    render_cmd,
    │    stdout=PIPE,
    │    stderr=PIPE,
    │    env={...}
    │  )
    ├─ Monitor progress:
    │  ├─ Parse stdout for frame-by-frame progress
    │  │  "V-Ray: Rendering frame 1…"
    │  │  "V-Ray: Frame 1 rendered in 42.3 seconds"
    │  │  "V-Ray: Rendering frame 2…"
    │  └─ Stream to server: POST /api/tasks/{id}/logs/
    │     { "log": "V-Ray: Rendering frame 2…", "timestamp": "..." }
    └─ Wait for completion

13. Render progress:
    Real-time feedback to dashboard:
    ├─ WebSocket event: task telemetry
    │  {"type": "task_progress", "task_id": "...", "percent_complete": 20}
    ├─ Dashboard updates:
    │  ├─ Job progress bar: 20/21 tasks = 95%
    │  ├─ Task row: "beauty 1-10: RUNNING (42s elapsed)"
    │  └─ Log tail: [live Maya output]
    └─ Repeat every 5 seconds

┌──────────────────────────────────────────────────────────────┐
│ PHASE 7: COMPLETION & RESULT PROCESSING                      │
└──────────────────────────────────────────────────────────────┘

14. Render completes (exit code 0):
    Worker TaskExecutor:
    ├─ Capture exit code: 0 ✓
    ├─ Collect final metrics:
    │  ├─ Duration: 423 seconds
    │  ├─ Frames rendered: 10
    │  ├─ Average frame time: 42.3 seconds
    │  └─ Peak memory: 8.9 GB
    ├─ Read output files:
    │  ├─ /storage/renders/PixarShort/010_intro/beauty/0001.exr ✓
    │  ├─ /storage/renders/PixarShort/010_intro/beauty/0002.exr ✓
    │  └─ ... 0010.exr ✓
    ├─ Report completion:
    │  POST /api/tasks/{task-1-uuid}/complete/
    │  {
    │    "exit_code": 0,
    │    "duration_seconds": 423,
    │    "peak_memory_gb": 8.9,
    │    "log_content": "V-Ray: Final render complete…"
    │  }
    └─ Clear temp directory

15. Backend process_task_result (Celery):
    ├─ Retrieve task & job
    ├─ Exit code == 0:
    │  ├─ task.state = SUCCEEDED
    │  ├─ task.completed_at = now
    │  ├─ job.succeeded_tasks += 1 (1 → 2)
    │  ├─ job.running_tasks -= 1 (2 → 1)
    │  └─ Update job.updated_at
    ├─ Check job completion:
    │  ├─ job.running_tasks == 0? (Yes: 1)
    │  ├─ job.ready_tasks == 0? (No: 18)
    │  └─ Job continues RUNNING
    └─ Emit WebSocket event:
       {"type": "task_state_changed", "task_id": "task-1-uuid", "new_state": "SUCCEEDED"}

16. Dashboard updates in real-time:
    ├─ WebSocket event received
    ├─ Refresh job view:
    │  ├─ Counters: "2 of 21 succeeded"
    │  ├─ Progress bar: 2/21 ≈ 10%
    │  ├─ Task row: [beauty 1-10] state changes to ✓ SUCCEEDED
    │  └─ Elapsed time: 423 seconds
    └─ Log viewer shows final output

┌──────────────────────────────────────────────────────────────┐
│ PHASE 8: REMAINING TASKS & COMPLETION                        │
└──────────────────────────────────────────────────────────────┘

17. Dispatcher continues (every 1 second):
    ├─ Resolve dependencies (same as step 7)
    ├─ Score remaining READY tasks
    ├─ Dispatch to available workers
    └─ Continue for all 20 remaining tasks

    Timeline (approximate):
    ├─ T+0s: 2 tasks dispatched (beauty 1-10, shadow 1-10)
    ├─ T+5s: Workers heartbeat, 2 more tasks claimed
    ├─ T+423s: First render complete, beauty 1-10 → SUCCEEDED
    ├─ T+425s: beauty 11-20 claimed
    ├─ T+500s: Next tasks complete…
    └─ T+4230s (≈1.2 hours): Last render (anim_output) completes
       └─ All beauty tasks SUCCEEDED
       └─ All shadow tasks SUCCEEDED
       └─ anim_output becomes READY (dependencies resolved)
       └─ anim_output claimed to available worker
       └─ Post-processing script runs
       └─ anim_output SUCCEEDED

18. Job reaches terminal state:
    ├─ job.running_tasks = 0 ✓
    ├─ job.ready_tasks = 0 ✓
    ├─ job.failed_tasks = 0 ✓
    └─ → job.state = FINISHED

    Update:
    ├─ job.stopped_at = now
    ├─ job.updated_at = now
    ├─ Emit WebSocket: {"type": "job_state_changed", "job_id": "...", "new_state": "FINISHED"}
    └─ Send notification (if configured)

┌──────────────────────────────────────────────────────────────┐
│ PHASE 9: POST-COMPLETION (Verification & Delivery)           │
└──────────────────────────────────────────────────────────────┘

19. Dashboard shows completion:
    ├─ Job state badge: "✓ FINISHED"
    ├─ Progress: 21/21 tasks completed
    ├─ All frames rendered: /storage/renders/PixarShort/010_intro/
    ├─ Logs available for download
    └─ Render outputs gallery (EXR sequence preview)

20. Artist verifies renders:
    ├─ Download output: scp -r /storage/renders/PixarShort/010_intro/ ~/renders/
    ├─ Load in Nuke/After Effects
    ├─ Review quality
    └─ Approve for delivery

21. Optional: Post-delivery
    ├─ Archive job metadata to S3
    ├─ Cleanup old renders (if retention policy)
    ├─ Generate report (duration, cost, efficiency)
    └─ Trigger downstream workflows (compositing, color, delivery)
```

---

## Render Commands by DCC

### Maya (Arnold, V-Ray)

**Basic Render**:

```bash
render.exe -rl beauty -fs 1 -fe 100 -x 1920 -y 1080 -of exr -pad 4 -rd /output/ scene.mb

# Flags:
-rl RenderLayer       # Render layer name
-fs FrameStart        # Starting frame
-fe FrameEnd          # Ending frame
-x Width              # Image width
-y Height             # Image height
-of FileFormat        # Output format (exr, jpg, etc.)
-pad Padding          # Frame number padding (4 = 0001)
-rd RenderDir         # Output directory
```

**Arnold-Specific**:

```bash
render.exe -rl beauty -fs 1 -fe 100 -ai:eaab 2 -ai:aasc 2 scene.mb

# Flags:
-ai:eaab              # Arnold samples per pixel
-ai:aasc              # Arnold AA seed count
```

**V-Ray-Specific**:

```bash
render.exe -rl beauty -fs 1 -fe 100 -vr 1 -rt 1 scene.mb

# Flags:
-vr 1                 # V-Ray enabled
-rt 1                 # Ray trace enabled
```

### Houdini

```bash
hrender -d /output/ -f 1 100 -e exr scene.hip

# Flags:
-d OutputDir          # Output directory
-f FrameStart FrameEnd # Frame range
-e OutputFormat       # File extension
```

### Blender

```bash
blender -b scene.blend -o /output/ -f 1 -s 1 -e 100 -F EXR -x 1 scene.blend

# Flags:
-b                    # Batch mode (headless)
-o OutputPath         # Output directory and format
-f FrameNumber         # Specific frame (not range)
-s StartFrame          # Start frame
-e EndFrame            # End frame
-F Format              # Output format
-x 1                   # Use compositor
```

### Custom Scripts

```bash
# Utility layer example:
python /projects/MyProject/scripts/cache_generator.py \
  --scene=/projects/MyProject/scenes/scene.hip \
  --frame-start=1 \
  --frame-end=100 \
  --output-dir=/cache/myproject/

# Post-processing example:
nuke -t /projects/MyProject/composites/final.nk \
  -F 1-100 \
  -x /projects/MyProject/renders/
```

---

## Error Handling & Retry Logic

### When Render Fails

```
Task renders but exits with non-zero code:

1. Worker detects exit_code != 0
2. POST /api/tasks/{id}/complete/ with exit_code=1
3. Celery process_task_result():
   ├─ task.retry_count < task.max_retries (0 < 3)?
   │  ├─ YES → task.state = READY (re-enter queue)
   │  ├─ Retry count incremented: 1
   │  └─ task.worker = None (unassigned)
   └─ NO (or max_retries = 0):
      ├─ task.state = FAILED
      ├─ job.running_tasks -= 1
      ├─ job.failed_tasks += 1
      └─ Job may transition to FAILED (if no skip)

4. If task.state = READY:
   └─ Next dispatch cycle (1 second later):
      ├─ Task re-enters scoring
      ├─ Retry penalty applied: 0.1 * retry_count
      │  └─ Score reduced by 10% per retry
      ├─ Task waits for available worker
      ├─ Worker claims task again
      └─ Render re-attempted

5. If task reaches max_retries and still fails:
   └─ Manual intervention:
      ├─ Admin can retry specific task
      ├─ Or skip task (unblocks job completion)
      ├─ Or increase max_retries and re-dispatch
```

### Common Failure Scenarios

| Failure             | Cause                         | Recovery                              |
| ------------------- | ----------------------------- | ------------------------------------- |
| **Out of Memory**   | Scene too heavy for worker    | Retry on bigger node, or split frames |
| **File Not Found**  | Texture/cache path broken     | Fix path, retry                       |
| **License Expired** | Render software license issue | Renew license, retry                  |
| **Timeout**         | Render hung for hours         | Kill process, retry or skip           |
| **Codec Error**     | Output format unavailable     | Change format, retry                  |
| **Disk Full**       | Output disk at capacity       | Free space, retry                     |

---

## Monitoring During Render

### Real-Time Telemetry

```
Every 5 seconds:

Worker sends to /api/workers/heartbeat/:
{
  "worker_id": "render-node-01",
  "telemetry": {
    "cpu_usage_percent": 89.2,
    "memory_usage_gb": 28.4,
    "memory_total_gb": 32.0,
    "gpu_count": 2,
    "gpu_memory_gb": [12.0, 12.0],
    "gpu_usage_percent": [95.3, 87.1],
    "network_latency_ms": 2.1
  }
}

Dashboard WebSocket receives:
{
  "type": "worker_telemetry_update",
  "worker_id": "render-node-01",
  "cpu_usage_percent": 89.2,
  "memory_usage_gb": 28.4,
  "gpu_usage_percent": [95.3, 87.1]
}

UI updates:
├─ Worker card: CPU bar filled 89%
├─ Worker card: Memory bar filled 89%
├─ GPU status: [95%] [87%] (high utilization)
└─ Dashboard metrics: Farm CPU avg = 62%
```

### Log Streaming

```
Worker captures task stdout in real-time:

render.exe output:
2025-01-15 11:45:00 | Maya 2024.1.1
2025-01-15 11:45:02 | Loading scene…
2025-01-15 11:45:05 | Arnold 7.2.3 loaded
2025-01-15 11:45:06 | V-Ray 6.0 loaded
2025-01-15 11:45:08 | Rendering frame 1…
2025-01-15 11:45:12 | GI Compute pass: 45% complete…
2025-01-15 11:45:50 | Frame 1 rendered in 42.3 seconds
2025-01-15 11:45:51 | Rendering frame 2…

Worker streams to backend:
POST /api/tasks/{id}/logs/ (every 100 lines or 5 seconds)
{
  "log_content": "2025-01-15 11:45:00 | Maya 2024.1.1\n2025-01-15 11:45:02 | Loading scene…\n…"
}

Dashboard log viewer:
└─ Tail: [Rendering frame 2…]
   [GI Compute pass: 45% complete…]
   [Frame 1 rendered in 42.3 seconds]

User can click "Download Logs" to get full log file.
```

---

## Performance Optimization

### Frame Batching

Default: 10 frames per task

```
Task 1: Frames 1-10
Task 2: Frames 11-20
Task 3: Frames 21-30
```

**Rationale**:

- Single frame = 100 tasks (overhead)
- 100 frames = 1 task (no parallelism)
- 10 frames = 10 tasks (balanced)

Can be configured per job.

### Deterministic Tie-Breaking

Without AI, dispatch is fully predictable:

```
1. Same priority = deterministic score (same every time)
2. Same score = frame order (frame 1 before frame 2)
3. No randomness = reproducible results
```

With AI tie-breaker:

```
Adds ~40ms latency per dispatch
Only for close-scoring tasks
Reduces unnecessary dispatch cycles
```

### Worker Pool Affinity

```
Job can specify:
├─ included_pools: ["GPU_STUDIO_A"]  # Only these pools
└─ excluded_pools: ["OFFLINE"]       # Never these pools

Dispatcher respects constraints:
├─ Filters workers before assignment
├─ Avoids wrong-capability nodes
└─ Reduces wasted dispatch-then-failure cycles
```

---

This system provides **scalable**, **fault-tolerant** distributed rendering with **real-time monitoring** and **intelligent scheduling**.
