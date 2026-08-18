import asyncio
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from prompts import SYSTEM_PROMPT, build_prompt

import httpx
import aiofiles

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RenderHive AI Scheduler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Configuration & State
# ---------------------------------------------------------------------------
# The service now supports dynamic model loading. It stores its config in
# config.json so the active model survives restarts.

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = Path(os.environ.get("MODELS_DIR", BASE_DIR / "models"))
MODELS_DIR.mkdir(exist_ok=True, parents=True)
CONFIG_FILE = MODELS_DIR / "config.json"

LLM = None
_llm_lock = threading.Lock()  # llama_cpp Llama objects are NOT thread-safe.
# asyncio.Lock for download state — must be asyncio-aware because _download_file
# is a coroutine. Using threading.Lock inside async def would block the event loop
# if ever contested, hanging all inference requests.
_download_lock: asyncio.Lock  # initialised in the startup event below

# Global state
active_config = {
    "model_path": os.environ.get("LLAMA_MODEL_PATH", ""),
    "prompt_template": os.environ.get("LLAMA_PROMPT_TEMPLATE", "mistral").lower(),
    "n_ctx": int(os.environ.get("LLAMA_N_CTX", "4096")),
    "n_threads": int(os.environ.get("LLAMA_THREADS", "4")),
}

# Maximum tasks to include in a single AI ranking call.
MAX_TASKS_PER_REQUEST = 10

# Download tracking
download_state = {
    "is_downloading": False,
    "filename": "",
    "bytes_downloaded": 0,
    "total_bytes": 0,
    "speed_bps": 0,
    "error": None,
    "cancel_requested": False,
}


def load_config():
    """Load config from config.json, updating the active_config."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_config.update(data)
                logger.info("Loaded configuration from config.json")
        except Exception as e:
            logger.error(f"Failed to read config.json: {e}")


def save_config():
    """Save active_config to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(active_config, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to write config.json: {e}")


def initialize_model():
    """Load the LLM based on active_config."""
    global LLM
    model_path = active_config["model_path"]
    n_ctx = active_config["n_ctx"]
    template = active_config["prompt_template"]

    with _llm_lock:
        if LLM is not None:
            del LLM  # Free previous memory
            LLM = None

        try:
            if model_path and os.path.exists(model_path):
                from llama_cpp import Llama
                LLM = Llama(
                    model_path=model_path,
                    n_gpu_layers=-1,
                    n_ctx=n_ctx,
                    n_threads=active_config.get("n_threads", 4),
                    verbose=False,
                )
                logger.info(f"Loaded LLaMA model from {model_path!r} (template: {template!r}, n_ctx: {n_ctx}, n_threads: {active_config.get('n_threads', 4)})")
            else:
                logger.warning(
                    f"Model path {model_path!r} not set or file not found. Running in MOCK mode."
                )
        except ImportError:
            logger.warning("llama-cpp-python not installed. Running in MOCK mode.")
        except Exception as e:
            logger.error(f"Failed to load LLaMA model: {e}. Running in MOCK mode.")


# Initialise on startup
@app.on_event("startup")
async def _startup():
    global _download_lock
    _download_lock = asyncio.Lock()
    load_config()
    initialize_model()


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

def _format_prompt(user_prompt: str) -> str:
    template = active_config["prompt_template"]
    if template == "llama3":
        return (
            "<|begin_of_text|>"
            "<|start_header_id|>system<|end_header_id|>\n\n"
            f"{SYSTEM_PROMPT}"
            "<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_prompt}"
            "<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
    elif template == "chatml":
        return (
            "<|im_start|>system\n"
            f"{SYSTEM_PROMPT}<|im_end|>\n"
            "<|im_start|>user\n"
            f"{user_prompt}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
    else:
        return (
            f"<|system|>\n{SYSTEM_PROMPT}</s>\n"
            f"<|user|>\n{user_prompt}</s>\n"
            "<|assistant|>\n"
        )


def _extract_json_array(text: str) -> str:
    import re
    import json
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    
    start = text.find("[")
    if start == -1:
        return text.strip()
        
    end = text.rfind("]")
    while end > start:
        candidate = text[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            end = text.rfind("]", 0, end)
            
    # Fallback: if we couldn't find a valid closing bracket, the LLM might have
    # generated a stop token immediately after the last object's `}` without closing the array.
    text = text.strip()
    if not text.endswith("]"):
        if text.endswith(","):
            text = text[:-1]
        try:
            # Test if appending a bracket makes it parseable
            test_candidate = text[start:] + "]"
            json.loads(test_candidate)
            return test_candidate
        except json.JSONDecodeError:
            pass
            
    return text


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CandidateTask(BaseModel):
    task_id: str
    priority: int
    base_score: float
    scene_info: Dict[str, Any]

class RankRequest(BaseModel):
    worker_caps: Dict[str, Any]
    tasks: List[CandidateTask]

class RankedTask(BaseModel):
    task_id: str
    score_delta: float
    reason: str

class DownloadRequest(BaseModel):
    url: str
    filename: str

class LoadModelRequest(BaseModel):
    filename: str
    prompt_template: str

# ---------------------------------------------------------------------------
# Endpoints: AI Dispatch
# ---------------------------------------------------------------------------

@app.post("/api/v1/rank-tasks", response_model=List[RankedTask])
def rank_tasks(req: RankRequest):
    if not req.tasks:
        return []
    if len(req.tasks) == 1:
        return [RankedTask(task_id=req.tasks[0].task_id, score_delta=0.0, reason="Only one candidate")]

    tasks = req.tasks[:MAX_TASKS_PER_REQUEST]
    if len(tasks) < len(req.tasks):
        logger.warning(f"Request truncated to {MAX_TASKS_PER_REQUEST} tasks.")

    if LLM is None:
        # §2 fix: use the already-capped `tasks` slice so mock and production
        # modes are behaviourally consistent (both respect MAX_TASKS_PER_REQUEST).
        return [
            RankedTask(task_id=t.task_id, score_delta=0.0, reason="Mock mode (no model loaded)")
            for t in tasks
        ]

    user_prompt = build_prompt(req.worker_caps, [t.model_dump() for t in tasks])
    full_prompt = _format_prompt(user_prompt)
    output_text = ""

    try:
        with _llm_lock:
            if LLM is None:
                return [
                    RankedTask(task_id=t.task_id, score_delta=0.0, reason="Mock mode (no model loaded)")
                    for t in tasks
                ]
            response = LLM(
                full_prompt,
                max_tokens=512,
                temperature=0.1,
                stop=["</s>", "<|eot_id|>", "<|im_end|>"],
            )

        output_text = response["choices"][0]["text"].strip()
        cleaned = _extract_json_array(output_text)
        parsed_json = json.loads(cleaned)

        if not isinstance(parsed_json, list):
            raise ValueError(f"LLM returned a non-list JSON structure: {type(parsed_json)}")

        ranked_tasks: List[RankedTask] = []
        for item in parsed_json:
            ranked_tasks.append(
                RankedTask(
                    task_id=item["task_id"],
                    score_delta=float(item.get("score_delta", 0.0)),
                    reason=str(item.get("reason", "")),
                )
            )

        scored_ids = {t.task_id for t in ranked_tasks}
        for t in req.tasks:
            if t.task_id not in scored_ids:
                ranked_tasks.append(
                    RankedTask(task_id=t.task_id, score_delta=0.0, reason="Missed by AI — zero delta applied")
                )

        return ranked_tasks

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON output: {e}\nRaw output was: {output_text!r}")
        return [RankedTask(task_id=t.task_id, score_delta=0.0, reason="LLM output parsing failed") for t in req.tasks]
    except Exception as e:
        logger.exception(f"LLM inference failed: {e}")
        raise HTTPException(status_code=500, detail="Inference failed")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": LLM is not None,
        "prompt_template": active_config["prompt_template"],
        "model_path": active_config["model_path"] or None,
        "n_ctx": active_config["n_ctx"],
        "max_tasks_per_request": MAX_TASKS_PER_REQUEST,
    }

# ---------------------------------------------------------------------------
# Endpoints: Model Management
# ---------------------------------------------------------------------------

CURATED_MODELS = [
    {
        "name": "Llama 3.2 1B Instruct (Q4)",
        "filename": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "template": "llama3",
        "size": "813 MB",
    },
    {
        "name": "Llama 3.2 3B Instruct (Q4)",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "template": "llama3",
        "size": "2.0 GB",
    },
    {
        "name": "Qwen 2.5 0.5B (Ultra-Light/CPU)",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "template": "chatml",
        "size": "398 MB",
    },
    {
        "name": "Qwen 2.5 1.5B (Light/CPU)",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "template": "chatml",
        "size": "1.1 GB",
    },
    {
        "name": "Mistral 7B Instruct (Q4)",
        "filename": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "url": "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "template": "mistral",
        "size": "4.1 GB",
    },
    {
        "name": "Qwen 2.5 7B Instruct (Q4)",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf",
        "template": "chatml",
        "size": "4.5 GB",
    },
    {
        "name": "Llama 3.1 8B Instruct (Q4)",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "template": "llama3",
        "size": "4.92 GB",
    },
]

@app.get("/api/v1/models")
def list_models():
    """List curated models and locally downloaded models."""
    local_files = []
    if MODELS_DIR.exists():
        for f in MODELS_DIR.iterdir():
            if f.is_file() and f.name.endswith(".gguf"):
                local_files.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                })
    return {
        "curated": CURATED_MODELS,
        "local": local_files,
        "active_path": active_config["model_path"]
    }


async def _download_file(url: str, dest_path: Path):
    global download_state
    temp_path = dest_path.with_suffix(".gguf.download")
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", 0))
                download_state["total_bytes"] = total
                download_state["bytes_downloaded"] = 0
                
                start_time = time.monotonic()
                bytes_since_last_check = 0
                last_check_time = start_time

                async with aiofiles.open(temp_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        if download_state.get("cancel_requested"):
                            raise Exception("Download cancelled by user.")
                        await f.write(chunk)
                        chunk_size = len(chunk)
                        download_state["bytes_downloaded"] += chunk_size
                        bytes_since_last_check += chunk_size
                        
                        now = time.monotonic()
                        if now - last_check_time >= 1.0:
                            speed = bytes_since_last_check / (now - last_check_time)
                            download_state["speed_bps"] = speed
                            bytes_since_last_check = 0
                            last_check_time = now

        if temp_path.exists():
            temp_path.rename(dest_path)

    except Exception as e:
        logger.error(f"Download failed: {e}")
        download_state["error"] = str(e)
    finally:
        if temp_path.exists():
            temp_path.unlink()
        download_state["is_downloading"] = False
        download_state["speed_bps"] = 0
        download_state["cancel_requested"] = False


@app.post("/api/v1/models/download")
async def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    """Start an async download of a model."""
    global download_state

    async with _download_lock:
        if download_state["is_downloading"]:
            raise HTTPException(status_code=400, detail="A download is already in progress.")

        dest_path = MODELS_DIR / req.filename
        if dest_path.exists():
            raise HTTPException(status_code=400, detail="File already exists.")

        download_state = {
            "is_downloading": True,
            "filename": req.filename,
            "bytes_downloaded": 0,
            "total_bytes": 0,
            "speed_bps": 0,
            "error": None,
            "cancel_requested": False,
        }

    background_tasks.add_task(_download_file, req.url, dest_path)
    return {"status": "started", "filename": req.filename}


@app.delete("/api/v1/models/download/cancel")
async def cancel_download():
    """Cancel an active download."""
    global download_state

    async with _download_lock:
        if not download_state["is_downloading"]:
            raise HTTPException(status_code=400, detail="No download in progress.")
        download_state["cancel_requested"] = True

    return {"status": "cancelling"}


@app.get("/api/v1/models/download/progress")
def get_download_progress():
    """Poll current download state."""
    return download_state


@app.post("/api/v1/models/load")
def load_model_endpoint(req: LoadModelRequest):
    """Dynamically swap the active model in RAM/VRAM."""
    model_path = MODELS_DIR / req.filename
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model file not found locally.")
        
    old_model_path = active_config["model_path"]
    old_template = active_config["prompt_template"]
    
    active_config["model_path"] = str(model_path.absolute())
    active_config["prompt_template"] = req.prompt_template.lower()
    
    # Reload model synchronously so we can return success/failure to the user
    initialize_model()
    
    if LLM is None:
        # Revert state if the model failed to load (e.g., Out of Memory)
        active_config["model_path"] = old_model_path
        active_config["prompt_template"] = old_template
        initialize_model() # try to restore old state
        raise HTTPException(status_code=500, detail="Failed to load model into memory (e.g. OOM). Check server logs.")
        
    # Only save to disk if successfully loaded
    save_config()
    return {"status": "ok", "message": f"Loaded {req.filename}"}


@app.post("/api/v1/models/unload")
def unload_model():
    """Unload the active model from memory."""
    active_config["model_path"] = ""
    save_config()
    initialize_model()
    return {"status": "unloaded"}


@app.delete("/api/v1/models/{filename}")
def delete_model(filename: str):
    """Delete a downloaded model from disk."""
    # §4: Allowlist — only .gguf files may be deleted through this endpoint.
    # This prevents path traversal variants and accidental deletion of
    # config.json or other files that live inside MODELS_DIR.
    if not filename.endswith(".gguf") or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename: must be a .gguf file without path separators")

    model_path = MODELS_DIR / filename
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    active_path = active_config["model_path"]
    if active_path and os.path.normpath(active_path) == os.path.normpath(str(model_path.absolute())):
        # Unload the model if it's currently active
        active_config["model_path"] = ""
        save_config()
        initialize_model()
        
    try:
        model_path.unlink()
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")
