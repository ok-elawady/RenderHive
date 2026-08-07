# AI Scheduler Service

> Part of the [RenderHive](../../README.md) platform — a dedicated microservice that uses a local LLM to intelligently break ties when multiple render tasks are equally viable for a worker.

---

## Overview

The AI Scheduler is a lightweight [FastAPI](https://fastapi.tiangolo.com/) service that runs a local LLM via [`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python). It acts exclusively as a **tie-breaker** within the RenderHive task dispatch pipeline.

The dispatch flow works in three phases:

```
Worker requests task
        │
        ▼
┌──────────────────────────────┐
│  Phase 1: BaseScorer         │  Deterministic scoring — priority, resource
│  (Django, no DB lock)        │  fit, failure penalty, frame order.
└──────────────┬───────────────┘
               │  Top tasks within 5% of each other?
               │  YES ──────────────────────────────────────────────────────┐
               │  NO                                                         │
               ▼                                                             ▼
┌─────────────────────────┐                              ┌───────────────────────────┐
│  Clear winner → bypass  │                              │  Phase 2: AI Tie-Breaker  │
│  AI entirely            │                              │  (this service, HTTP)     │
└───────────┬─────────────┘                              └──────────┬────────────────┘
            │                                                        │
            └─────────────────────┬──────────────────────────────────┘
                                  ▼
              ┌──────────────────────────────────┐
              │  Phase 3: Atomic DB claim        │
              │  (select_for_update, winner only) │
              └──────────────────────────────────┘
```

By only invoking the LLM when tasks are genuinely competitive, the service stays out of the hot path for the vast majority of dispatches.

---

## Configuration

All settings are controlled via environment variables (see [`.env.example`](../../.env.example)).

| Variable | Default | Description |
|---|---|---|
| `LLAMA_MODEL_PATH` | *(empty)* | Absolute path to a `.gguf` model file. If empty, runs in **mock mode**. |
| `LLAMA_PROMPT_TEMPLATE` | `mistral` | Chat template format. See [Prompt Templates](#prompt-templates). |

### Prompt Templates

The correct template **must** match your model family or the LLM will not follow the system prompt correctly.

| Value | Model Families |
|---|---|
| `mistral` | Mistral 7B Instruct, Zephyr, Mistral Instruct v2/v3 |
| `llama3` | Meta Llama 3 Instruct, Llama 3.1, Llama 3.2 |
| `chatml` | Mistral Nemo, Qwen2, Phi-3, OpenHermes |

### Recommended Models

This service is designed for lightweight local models. The LLM's job is structured reasoning over small JSON payloads, not creative generation, so a 4-bit quantised 7B model is more than sufficient.

| Model | Size (Q4) | Template | Notes |
|---|---|---|---|
| `mistral-7b-instruct-v0.2.Q4_K_M.gguf` | ~4.1 GB | `mistral` | Reliable, well-tested for structured JSON |
| `Meta-Llama-3-8B-Instruct.Q4_K_M.gguf` | ~4.9 GB | `llama3` | Strong instruction following |
| `Qwen2.5-7B-Instruct.Q4_K_M.gguf` | ~4.4 GB | `chatml` | Excellent JSON output discipline |

Download GGUF models from [Hugging Face](https://huggingface.co/) (look for `TheBloke` or official model repos).

---

## Running Locally

### With Docker Compose (recommended)

The service runs under the `ai` Docker Compose profile so it does not start by default.

```bash
# Start the full RenderHive stack including the AI Scheduler
docker compose --profile ai up --build

# The service will be available at http://localhost:8001
# The Django API on http://localhost:8000 will connect to it automatically
```

To point the service at a model file, set `LLAMA_MODEL_PATH` in your `.env`:

```env
LLAMA_MODEL_PATH=/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
LLAMA_PROMPT_TEMPLATE=mistral
```

Then copy your `.gguf` file into the `models` Docker volume, or switch to a bind mount in `docker-compose.yml`.

### Without Docker (development)

```bash
cd services/ai_scheduler
pip install -r requirements.txt

# Mock mode (no model required)
uvicorn main:app --reload --port 8001

# With a real model
LLAMA_MODEL_PATH=/path/to/model.gguf LLAMA_PROMPT_TEMPLATE=mistral \
  uvicorn main:app --reload --port 8001
```

---

## API

### `POST /api/v1/rank-tasks`

Accepts a worker's capabilities and a list of candidate tasks. Returns them ranked with score deltas and reasoning.

**Request:**
```json
{
  "worker_caps": {
    "hostname": "render-node-01",
    "cores": 32,
    "memory_mb": 131072,
    "gpu_models": ["NVIDIA RTX 4090"],
    "live_metrics": { "cpu_percent": 12.0, "gpu_percent": 0.0 }
  },
  "tasks": [
    {
      "task_id": "uuid-a",
      "priority": 80,
      "base_score": 0.412,
      "scene_info": { "renderer": "redshift", "resolution": [3840, 2160] }
    },
    {
      "task_id": "uuid-b",
      "priority": 80,
      "base_score": 0.410,
      "scene_info": { "renderer": "arnold", "resolution": [1920, 1080] }
    }
  ]
}
```

**Response:**
```json
[
  { "task_id": "uuid-a", "score_delta": 0.12, "reason": "Redshift GPU render benefits from the idle RTX 4090 and 128GB RAM." },
  { "task_id": "uuid-b", "score_delta": -0.05, "reason": "Arnold CPU render does not leverage the available GPU." }
]
```

Score deltas are clamped to `±0.20` by the Django client before being applied, preventing the AI from overriding job priorities set by artists.

### `GET /health`

Returns service health and model load status.

```json
{
  "status": "ok",
  "model_loaded": true,
  "prompt_template": "mistral",
  "model_path": "/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
}
```

---

## Mock Mode

When `LLAMA_MODEL_PATH` is not set, the service runs in **mock mode**: it returns random score deltas instead of real LLM inference. This is intentional and useful for:

- Local development without a GPU or large model file
- Testing the full tie-breaker dispatch path end-to-end
- CI/CD environments

The Django fallback (`SCHEDULER_AI_ENABLED=False` or a timeout/network error) always falls back to pure deterministic scoring, so the farm operates correctly regardless of whether this service is running.

---

## Observability

Every dispatched task stores a `last_score_breakdown` JSON blob in the database (visible in Django Admin under **Jobs → Tasks**). This shows exactly what score each factor contributed and whether the AI was invoked.

Example breakdown:
```json
{
  "job_priority": 0.32,
  "failure_penalty": 0.0,
  "resource_fit": 0.18,
  "dispatch_order": -0.002,
  "ai_adjustment": 0.12,
  "ai_reason": "Redshift GPU render benefits from the idle RTX 4090."
}
```
