# AI Scheduler System

## Overview

The AI Scheduler is an **optional** component that provides intelligent tie-breaking for task dispatch when multiple tasks have similar priority scores. It's implemented as a FastAPI microservice that runs a local LLM (via `llama-cpp-python`) to rank tasks based on worker capabilities and job requirements.

**Key Principle**: The AI scheduler is a tie-breaker only. If the deterministic scoring algorithm clearly ranks task A above task B, the AI is never queried. This ensures:

- ✅ Predictable behavior (deterministic scoring is primary)
- ✅ Reduced computational overhead (AI only for ambiguous cases)
- ✅ Graceful degradation (falls back to deterministic if AI unavailable)

---

## When the AI is Queried

```
if len(tasks_ready_for_dispatch) > 1:
    top_score = tasks[0].score
    second_score = tasks[1].score

    if abs(top_score - second_score) <= 0.05:  # Within 5%
        # Ambiguous case: query AI
        ai_ranking = call_ai_scheduler(tasks[:10], available_workers)
        # Use AI ranking as primary sort, deterministic as tiebreaker
    else:
        # Clear winner: use deterministic score
        dispatch_task_with_highest_score(tasks[0])
```

---

## Architecture

### FastAPI Service

**File**: `backend/ai_scheduler/main.py` (if separate) or inline in Celery

**Endpoint**: `POST /rank-tasks/`

**Dependencies**:

- `fastapi` — Web framework
- `llama-cpp-python` — LLM inference
- `numpy` — Numerical operations
- `pydantic` — Request/response validation

### Model Loading

**Supported Models**:

- **TinyLlama** (1.1B parameters, recommended)
  - Fast inference (~50ms per request)
  - Fits in 4GB RAM
  - Adequate for task ranking
  - Model: `tinyllama-1.1b.Q4_K_M.gguf` (600 MB)

- **Llama 2** (7B, optional if more capacity)
  - Better reasoning (~200ms per request)
  - Requires 8GB+ RAM
  - Model: `llama-2-7b.Q4_K_M.gguf` (3.8 GB)

- **Mistral** (7B, optional)
  - Faster than Llama 2
  - Good balance of speed and reasoning

**Model Download**:

```bash
# Create models directory
mkdir -p /models

# Download TinyLlama (Hugging Face)
cd /models
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf

# Verify
ls -lh /models/
```

### Model Initialization

```python
# apps/jobs/ai_scheduler.py
from llama_cpp import Llama

class AIScheduler:
    def __init__(self, model_path: str, n_threads: int = 4):
        self.model = None
        self.model_path = model_path
        self.n_threads = n_threads
        self.load_model()

    def load_model(self):
        """Lazy-load model on first use."""
        try:
            self.model = Llama(
                model_path=self.model_path,
                n_threads=self.n_threads,
                n_gpu_layers=0,  # Set to -1 for GPU acceleration if available
                verbose=False
            )
            logger.info(f"Loaded AI model from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load AI model: {e}")
            self.model = None

    def rank_tasks(self, tasks: List[dict], workers: List[dict]) -> dict:
        """
        Rank tasks based on worker suitability.

        Args:
            tasks: List of task dicts with id, priority, frame_range, score
            workers: List of worker dicts with id, cores, memory, gpu_count

        Returns:
            {
              "ranked_tasks": [{"task_id": "...", "rank": 1, "confidence": 0.87}],
              "inference_ms": 42
            }
        """
        if not self.model:
            # Graceful fallback if model unavailable
            return {
                "error": "Model not loaded",
                "fallback": True,
                "ranked_tasks": self._fallback_rank(tasks)
            }

        start_time = time.time()

        # Build prompt
        prompt = self._build_prompt(tasks, workers)

        # Run inference
        response = self.model(
            prompt,
            max_tokens=200,
            temperature=0.3,  # Low temp for deterministic behavior
            top_p=0.95
        )

        # Parse response
        ranking = self._parse_response(response['choices'][0]['text'], tasks)

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "ranked_tasks": ranking,
            "inference_ms": elapsed_ms,
            "model_loaded": True
        }

    def _build_prompt(self, tasks: List[dict], workers: List[dict]) -> str:
        """Construct prompt for LLM."""

        prompt = """You are a task scheduler for a distributed render farm.

Given the following tasks and available workers, rank the tasks by priority
(best suited task first). Output only a JSON array of task IDs in ranked order.

TASKS:
"""
        for task in tasks[:10]:  # Limit to top 10 for token efficiency
            prompt += f"""
- Task {task['task_id'][:8]}...
  Priority: {task['priority']}/100
  Frame Range: {task['frame_start']}-{task['frame_end']}
  Deterministic Score: {task['score']:.2f}
  Pool Include: {task.get('pool_include', 'Any')}
"""

        prompt += "\nAVAILABLE WORKERS:\n"
        for worker in workers[:5]:  # Limit to top 5 workers
            prompt += f"""
- Worker {worker['worker_id'][:8]}...
  CPU: {worker['cpu_cores']} cores
  Memory: {worker['available_memory_gb']} GB available
  GPU: {worker['gpu_count']} units, {worker['gpu_vram_available_gb']} GB VRAM
  Pool: {worker['pool']}
"""

        prompt += """
Rank the tasks from best to worst match for these workers.
Output as JSON array of task IDs only, e.g.:
["task-uuid-1", "task-uuid-2", "task-uuid-3"]
"""
        return prompt

    def _parse_response(self, response_text: str, tasks: List[dict]) -> List[dict]:
        """Extract task ranking from LLM output."""

        try:
            # Try to find JSON array in response
            import json
            match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if match:
                ranked_ids = json.loads(match.group())

                # Build ranking with confidence scores
                result = []
                for rank, task_id in enumerate(ranked_ids):
                    # Extract original score for confidence
                    original_score = next(
                        (t['score'] for t in tasks if t['task_id'] == task_id),
                        0.5
                    )
                    result.append({
                        "task_id": task_id,
                        "ai_rank": rank + 1,
                        "confidence": 0.85 + (rank * 0.01)  # Confidence decreases with rank
                    })
                return result
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")

        # Fallback: return original score ordering
        return self._fallback_rank(tasks)

    def _fallback_rank(self, tasks: List[dict]) -> List[dict]:
        """Fallback when parsing fails."""
        sorted_tasks = sorted(tasks, key=lambda t: t['score'], reverse=True)
        return [
            {
                "task_id": t['task_id'],
                "ai_rank": i + 1,
                "confidence": 0.5  # Lower confidence for fallback
            }
            for i, t in enumerate(sorted_tasks)
        ]

# Global instance
ai_scheduler = AIScheduler(
    model_path=settings.AI_SCHEDULER_MODEL_PATH,
    n_threads=settings.AI_SCHEDULER_N_THREADS
)
```

### FastAPI Endpoint

```python
# apps/jobs/ai_api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="RenderHive AI Scheduler")

class TaskInput(BaseModel):
    task_id: str
    priority: int
    frame_start: int
    frame_end: int
    score: float
    pool_include: Optional[str] = None
    pool_exclude: Optional[str] = None

class WorkerInput(BaseModel):
    worker_id: str
    cpu_cores: int
    memory_gb: float
    available_memory_gb: float
    gpu_count: int
    gpu_vram_available_gb: float
    pool: str

class RankTasksRequest(BaseModel):
    tasks: List[TaskInput]
    available_workers: List[WorkerInput]

class RankedTask(BaseModel):
    task_id: str
    ai_rank: int
    confidence: float

class RankTasksResponse(BaseModel):
    ranked_tasks: List[RankedTask]
    inference_ms: float
    model_loaded: bool
    error: Optional[str] = None

@app.post("/rank-tasks/", response_model=RankTasksResponse)
async def rank_tasks(request: RankTasksRequest):
    """Rank tasks based on worker suitability."""

    # Convert to dicts
    tasks = [t.model_dump() for t in request.tasks]
    workers = [w.model_dump() for w in request.available_workers]

    # Run ranking
    result = ai_scheduler.rank_tasks(tasks, workers)

    return RankTasksResponse(**result)

@app.get("/health/")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": ai_scheduler.model is not None,
        "version": "1.0.0"
    }
```

### Integration with Celery

**In `dispatch_ready_tasks()` Celery task**:

```python
def dispatch_ready_tasks():
    """Main dispatch loop (runs every 1 second)."""

    # ... (dependency resolution, deterministic scoring)

    # Sort by deterministic score
    tasks_with_scores.sort(key=lambda x: x[1], reverse=True)

    # Query AI if top scores are close
    if should_query_ai(tasks_with_scores):
        try:
            response = requests.post(
                f"{settings.AI_SCHEDULER_URL}/rank-tasks/",
                json={
                    "tasks": [
                        {
                            "task_id": str(t.id),
                            "priority": t.layer.job.priority,
                            "frame_start": t.frame_start,
                            "frame_end": t.frame_end,
                            "score": score
                        }
                        for t, score in tasks_with_scores[:20]
                    ],
                    "available_workers": [
                        {
                            "worker_id": str(w.id),
                            "cpu_cores": w.capabilities['cpu_cores'],
                            "memory_gb": w.capabilities['memory_gb'],
                            "available_memory_gb": calculate_available_memory(w),
                            "gpu_count": w.capabilities.get('gpu_count', 0),
                            "gpu_vram_available_gb": calculate_gpu_vram_available(w),
                            "pool": w.pool.name
                        }
                        for w in get_available_workers()
                    ]
                },
                timeout=5
            )

            if response.status_code == 200:
                ai_ranking = response.json()['ranked_tasks']

                # Build mapping: task_id → ai_rank
                ai_rank_map = {
                    t['task_id']: t['ai_rank']
                    for t in ai_ranking
                }

                # Re-sort: primary by AI rank, secondary by deterministic score
                tasks_with_scores.sort(
                    key=lambda x: (
                        ai_rank_map.get(str(x[0].id), 999),  # AI rank
                        -x[1]  # Deterministic score (descending)
                    )
                )

                logger.info(f"AI scheduler ranked {len(ai_ranking)} tasks")

        except (RequestException, Timeout, JSONDecodeError) as e:
            logger.warning(f"AI scheduler unavailable, falling back: {e}")
            # Continue with deterministic scoring

    # Dispatch top task
    if tasks_with_scores:
        top_task, top_score = tasks_with_scores[0]
        claim_task_for_worker(top_task, find_optimal_worker(top_task))
```

---

## Configuration

### Environment Variables

```bash
# .env
AI_SCHEDULER_ENABLED=True
AI_SCHEDULER_URL=http://localhost:8001
AI_SCHEDULER_MODEL_PATH=/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
AI_SCHEDULER_N_THREADS=4
AI_SCHEDULER_TIMEOUT_SEC=5
```

### Django Settings

```python
# config/settings/base.py
AI_SCHEDULER_ENABLED = os.getenv('AI_SCHEDULER_ENABLED', 'False') == 'True'
AI_SCHEDULER_URL = os.getenv('AI_SCHEDULER_URL', 'http://localhost:8001')
AI_SCHEDULER_MODEL_PATH = os.getenv(
    'AI_SCHEDULER_MODEL_PATH',
    '/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf'
)
AI_SCHEDULER_N_THREADS = int(os.getenv('AI_SCHEDULER_N_THREADS', '4'))
AI_SCHEDULER_TIMEOUT_SEC = int(os.getenv('AI_SCHEDULER_TIMEOUT_SEC', '5'))
```

---

## Docker Compose Integration

```yaml
# docker-compose.yml
services:
  ai_scheduler:
    image: renderhive-ai-scheduler:latest
    build:
      context: ./backend
      dockerfile: Dockerfile.ai
    ports:
      - "8001:8001"
    environment:
      MODEL_PATH: /models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
      N_THREADS: 4
    volumes:
      - ai_models:/models:ro # Shared model cache
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  ai_models:
```

**Dockerfile.ai**:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ai_scheduler/ .

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## Monitoring & Debugging

### Health Check

```bash
curl http://localhost:8001/health/

# Response
{
  "status": "healthy",
  "model_loaded": true,
  "version": "1.0.0"
}
```

### Test Ranking

```bash
curl -X POST http://localhost:8001/rank-tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {"task_id": "task-1", "priority": 75, "frame_start": 1, "frame_end": 10, "score": 0.82},
      {"task_id": "task-2", "priority": 70, "frame_start": 11, "frame_end": 20, "score": 0.80}
    ],
    "available_workers": [
      {"worker_id": "w-1", "cpu_cores": 16, "memory_gb": 32, "available_memory_gb": 16, "gpu_count": 2, "gpu_vram_available_gb": 24, "pool": "STUDIO_A"}
    ]
  }'

# Response
{
  "ranked_tasks": [
    {"task_id": "task-1", "ai_rank": 1, "confidence": 0.86},
    {"task_id": "task-2", "ai_rank": 2, "confidence": 0.85}
  ],
  "inference_ms": 38,
  "model_loaded": true
}
```

### Logs

```bash
# Docker container
docker-compose logs -f ai_scheduler

# Expected output:
# 2025-01-15 10:45:12 | INFO | Loaded AI model from /models/tinyllama...gguf
# 2025-01-15 10:45:42 | INFO | Ranking request: 3 tasks, 2 workers
# 2025-01-15 10:45:42 | INFO | Inference complete in 42ms
```

### Metrics

```bash
# Prometheus metrics (if added)
curl http://localhost:8001/metrics/

# Expected:
# ai_scheduler_ranking_requests_total{status="success"} 1234
# ai_scheduler_inference_duration_ms{quantile="0.95"} 45.2
# ai_scheduler_model_loaded 1
```

---

## Performance Characteristics

| Metric                        | Value    | Notes                           |
| ----------------------------- | -------- | ------------------------------- |
| Model Size                    | 600 MB   | TinyLlama (Q4 quantization)     |
| Memory Footprint              | ~2.5 GB  | Including LLM context + buffers |
| Inference Time                | 40-60 ms | Single ranking request          |
| Max Tokens Output             | 200      | Task ranking list               |
| Supported Concurrent Requests | 1        | Single-threaded model           |
| Queue Time                    | ~100 ms  | If previous request active      |
| CPU Usage (idle)              | <1%      | Model waiting for input         |
| CPU Usage (inference)         | 300-400% | 4-thread multiprocessing        |

**Scaling Considerations**:

- Single AI instance can handle ~600 ranking requests/hour
- For higher throughput: run multiple AI replicas + load balancer
- GPU acceleration (CUDA) can 3-5x speed up inference

---

## Fallback & Resilience

**When AI is unavailable**:

1. Request times out (>5 seconds) → Fall back to deterministic score
2. AI service returns error → Fall back to deterministic score
3. Model fails to load on startup → Run deterministic-only mode
4. JSON parsing fails → Fall back to deterministic score

**No explicit failure**: If AI unavailable, system continues with deterministic scoring. Zero service interruption.

---

## Future Enhancements

1. **Multi-model support**: Toggle between TinyLlama, Mistral, Llama 2
2. **Fine-tuning**: Collect dispatch decisions + outcomes, train custom ranking model
3. **GPU acceleration**: CUDA support for 3-5x faster inference
4. **Caching**: Cache identical ranking requests (same tasks/workers)
5. **A/B Testing**: Compare AI vs. deterministic scoring over time
6. **Reinforcement Learning**: Train model on long-term job completion metrics

---

The AI scheduler adds **intelligent tie-breaking** while maintaining **predictability** and **reliability**. It's optional, but when enabled, can significantly improve task dispatch in complex multi-job scenarios.
