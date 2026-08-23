# RenderHive: Project Overview

## What is RenderHive?

RenderHive is a **distributed render farm management platform** designed for modern 3D digital content creation (DCC) pipelines. It coordinates render jobs, intelligently schedules tasks across worker nodes, and integrates seamlessly with industry-standard tools like Autodesk Maya and SideFX Houdini.

Think of it as a **sophisticated task dispatcher** for rendering: when you submit a render job, RenderHive breaks it into atomic tasks, queues them, distributes them to available worker nodes, tracks progress in real-time, and handles failures with automatic retry logic.

---

## The Problem It Solves

**Manual render management is broken:**

- **Single-machine bottleneck**: One workstation can only render one frame at a time
- **No visibility**: You don't know which jobs are queued, running, or failing
- **No optimization**: Tasks are dispatched randomly without considering worker capabilities
- **Manual failover**: If a machine crashes, rendering stops
- **DCC friction**: Artists must manually manage file paths, logs, and job tracking outside their tools

**RenderHive fixes this by:**

1. **Distributing rendering** across multiple worker nodes automatically
2. **Intelligent task scheduling** using deterministic scoring + optional AI tie-breaking
3. **Real-time monitoring** with a modern web dashboard
4. **Automatic failure recovery** with configurable retry logic
5. **Seamless DCC integration** so artists submit jobs without leaving Maya
6. **Worker pool management** to target specific hardware (GPUs, disk speed, software versions)

---

## Key Features

### 1. **Distributed Task Dispatch**

- Job → Layer → Task hierarchy
- Deterministic scoring based on priority, resource fit, and failure penalties
- Optional LLM tie-breaker when tasks are equally viable
- Worker pool targeting (include/exclude specific worker pools)

### 2. **AI-Augmented Scheduling** (Optional)

- A FastAPI microservice running a local LLM (llama-cpp-python)
- Acts as a **tie-breaker** only when multiple tasks have very similar scores
- Falls back to pure deterministic scoring if AI is unavailable
- Reduces wasted dispatch cycles while avoiding over-computation

### 3. **Real-Time Web Dashboard**

- Modern React/Next.js interface with Tailwind CSS v4
- Live job queue monitoring
- Worker node status and utilization
- Task dependency graph visualization
- Farm-wide metrics (CPU, memory, GPU VRAM)
- Activity feed and telemetry

### 4. **DCC Integrations**

- **Maya Plugin**: Drag-and-drop installer, job submitter UI, scene validation
- Scene state preservation and recovery
- Layer-to-task mapping with render layer support
- Dependency modeling (Job-on-Job, Layer-on-Layer, Task-on-Task)

### 5. **Worker Management**

- Desktop worker application (PySide6 Qt UI)
- Automatic worker discovery and pool assignment
- Per-worker capability tracking (Maya versions, GPU models, CPU cores, RAM)
- Health monitoring and offline detection (30-second stale threshold)
- Telemetry collection (CPU, memory, GPU utilization)

### 6. **Robust Task Execution**

- Max retry logic with exponential backoff
- Checkpoint support for interruption-safe rendering
- Frame-level granularity (individual frames can be requeued)
- Dependency enforcement before task release
- Timeout detection and cleanup

---

## Core Technology Stack

| Component              | Technology                                         | Purpose                                            |
| ---------------------- | -------------------------------------------------- | -------------------------------------------------- |
| **Frontend**           | Next.js 16, React 19, Tailwind CSS v4, Shadcn UI   | Modern, responsive web dashboard                   |
| **Backend API**        | Django 5.2, Django REST Framework, drf-spectacular | RESTful orchestration + OpenAPI docs               |
| **Authentication**     | django-allauth (headless)                          | Browser sessions + token auth for workers          |
| **Database**           | PostgreSQL 16                                      | Persistent job, layer, task, worker state          |
| **Cache & Queue**      | Redis 7                                            | Session cache, Celery broker, result backend       |
| **Background Tasks**   | Celery + django-celery-beat                        | Scheduled telemetry, worker reaping, health checks |
| **AI Scheduler**       | FastAPI + llama-cpp-python                         | Local LLM inference for tie-breaking               |
| **Worker Application** | Python + PySide6                                   | Desktop UI for render nodes                        |
| **DCC Plugins**        | Python + MEL (Maya)                                | Scene submission, validation, integration          |
| **Containerization**   | Docker + Docker Compose                            | Development and production deployment              |

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                       ARTIST / USER TIER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Maya Plugin ◄──────────► DCC Validation ─────┐                 │
│                                               │                 │
│  Web Dashboard ◄─────────────────────────────►│                 │
│  (Job Queue, Monitoring, Settings)            │                 │
│                                                │                 │
└────────────────────────────────────────────────┼──────────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Django REST API (http://localhost:8000)                        │
│  ├─ /api/jobs/          → Job CRUD + state transitions         │
│  ├─ /api/workers/       → Worker pool + node management        │
│  ├─ /api/dependencies/  → Dependency graph                     │
│  └─ /api/users/me/      → Profile + auth                       │
│                                                                   │
│  Celery Worker (Distributed Task Broker)                        │
│  ├─ Task scoring & dispatch                                     │
│  ├─ Worker health monitoring                                    │
│  └─ Telemetry collection                                        │
│                                                                   │
│  Celery Beat (Scheduler)                                        │
│  ├─ Worker reap cycle (every 15s)                              │
│  ├─ Telemetry aggregation (every 60s)                          │
│  └─ Stale worker detection (30s threshold)                     │
│                                                                   │
│  AI Scheduler Service (FastAPI, optional)                       │
│  └─ LLM-powered tie-breaker for competitive tasks              │
│                                                                   │
└────────────────────────────────────────────────────────────────┘
     │                  │                      │
     ▼                  ▼                      ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ PostgreSQL   │   │    Redis     │   │ S3 / Storage │
│ (persisted   │   │ (sessions,   │   │ (job logs,   │
│  state)      │   │  cache)      │   │  renders)    │
└──────────────┘   └──────────────┘   └──────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       WORKER / RENDER TIER                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Worker Node 1 (render-node-01)                                 │
│  ├─ Worker App (PySide6 UI)                                    │
│  ├─ Task Executor (claim → render → report)                    │
│  ├─ Telemetry (CPU, RAM, GPU metrics)                          │
│  └─ DCC Runtime (Maya 2023, Houdini 20, etc.)                  │
│                                                                   │
│  Worker Node 2, 3, ... N                                        │
│  (Same architecture, pooled for distribution)                   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Complete Render Job Lifecycle

```
1. SUBMISSION
   Artist opens Maya → RenderHive Submitter Plugin
   → Configures job (project, priority, pool targeting)
   → Selects render layers
   → Validates scene (geometry, materials, render settings)
   → Submits

2. INGESTION
   Backend receives Job + Layer + Task payload
   → Job state = PENDING
   → Tasks state = WAITING (blocked by dependencies)
   → Counter caches initialized
   → Stored in PostgreSQL

3. DEPENDENCY RESOLUTION
   Celery worker runs every tick
   → Check if task dependencies are satisfied
   → WAITING → READY (unblocked)
   → Ready tasks enter dispatch queue

4. TASK SCORING (Deterministic)
   For each READY task:
   → Calculate base score:
      • Job priority (1-100)
      • Resource fit (worker cores, memory vs. task requirements)
      • Failure penalty (tasks that failed before get lower scores)
      • Frame order (favor lower frame numbers)

5. AI TIE-BREAKING (Optional)
   If multiple tasks have scores within 5% of each other:
   → Serialize top tasks as JSON
   → Send to AI Scheduler service (FastAPI)
   → LLM ranks them based on worker capabilities
   → If AI unavailable, use deterministic score

6. WORKER CLAIM
   Worker sends heartbeat → "Give me a task"
   → Backend selects winning task
   → Atomic DB claim (select_for_update)
   → Task state = RUNNING
   → Assigned to worker

7. EXECUTION
   Worker pulls task details
   → Checks for render software (Maya, Houdini, etc.)
   → Verifies compatibility (version, GPU requirements)
   → Executes command (e.g., `render.exe -rl beauty -fs 1 -fe 100`)
   → Captures stdout/stderr
   → Streams progress

8. MONITORING
   Dashboard polls real-time metrics:
   → Task status (RUNNING)
   → Worker utilization (CPU, RAM, GPU)
   → Progress (0-100% estimated)
   → Logs streamed to storage

9. COMPLETION
   Worker reports result:
   → Exit code 0 → Task state = SUCCEEDED
   → Exit code ≠ 0 → Task state = FAILED
   → Increments job counter caches
   → Stores final metrics and logs

10. RETRY LOGIC
    If task failed:
    → Check retries < max_retries
    → Increment retry counter
    → Task state = READY (re-enter queue)
    → Go back to step 4 (scoring)

    If retries exhausted:
    → Task state = FAILED (final)
    → Job checks: any failed tasks?
    → Job state = FINISHED (if all succeeded/skipped)
    → Job state = FAILED (if any failed beyond retries)

11. REPORTING
    Dashboard updated:
    → Job progress (% complete)
    → Task breakdown (succeeded, failed, skipped)
    → Render outputs collected
    → Logs available for download
```

---

## Who Should Use RenderHive?

| Role                      | Use Case                                              |
| ------------------------- | ----------------------------------------------------- |
| **VFX/Animation Studios** | Manage 100+ concurrent render jobs across departments |
| **Individual Artists**    | Render at home on a 5-node cluster                    |
| **Game Dev Teams**        | Distribute shader builds and texture processing       |
| **Architectural Viz**     | Batch render across different lighting scenarios      |
| **Post-Production**       | Distribute color grading, compression, transcoding    |

---

## Key Strengths

✅ **No Single Point of Failure** — Distributed architecture with health monitoring  
✅ **Intelligent Scheduling** — AI tie-breaking optional; deterministic fallback always available  
✅ **Artist-Friendly** — Direct integration into Maya via drag-and-drop plugin  
✅ **Transparent Monitoring** — Real-time dashboard with dependency graphs  
✅ **Extensible** — Plugin system allows Houdini, Blender, custom DCCs  
✅ **Open Source Ready** — Clean, documented Python/TypeScript codebase

---

## Current Implementation Status

| Component          | Status              | Notes                                                |
| ------------------ | ------------------- | ---------------------------------------------------- |
| Core API           | ✅ Production-ready | Full CRUD for jobs, layers, tasks, dependencies      |
| Database Schema    | ✅ Complete         | PostgreSQL with proper indexes and migrations        |
| Worker Application | ✅ Stable           | PySide6 UI with telemetry collection                 |
| Maya Plugin        | ✅ v2.0.0           | Full validation, submission, state recovery          |
| Dashboard          | ✅ MVP              | Dashboard, job queue, monitoring (Next.js)           |
| AI Scheduler       | ✅ Functional       | FastAPI with llama-cpp-python, dynamic model loading |
| Authentication     | ✅ Working          | Django-allauth headless + browser/token auth         |
| Houdini Plugin     | ❌ Not yet          | Planned but not implemented                          |
| Blender Plugin     | ❌ Not yet          | Planned but not implemented                          |

---

## Next Steps for New Developers

1. **Read the architecture docs** → `02-architecture.md`
2. **Set up locally** → `03-setup.md`
3. **Explore the frontend** → `04-frontend.md`
4. **Explore the backend** → `05-backend.md`
5. **Understand the AI system** → `06-ai-system.md`
6. **Run a test render** → `03-setup.md` (Complete Setup & Running Guide)

---

## Questions?

- **How do jobs get scheduled?** See `08-rendering-system.md`
- **How do workers authenticate?** See `05-backend.md` (Authentication)
- **How does the AI tie-breaker work?** See `06-ai-system.md`
- **How do I add a new DCC plugin?** See `07-plugin-system.md`
- **How do I troubleshoot a failed render?** See `14-troubleshooting.md`
