import json
import logging
import os
import re
import random
import threading
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from prompts import SYSTEM_PROMPT, build_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RenderHive AI Scheduler")

# ---------------------------------------------------------------------------
# LLM Initialisation
# ---------------------------------------------------------------------------
# The model is loaded once at startup and reused across requests.
# LLAMA_MODEL_PATH: absolute path to a GGUF model file.
# LLAMA_PROMPT_TEMPLATE: chat template family for the loaded model.
#   Supported values: "mistral" (default), "llama3", "chatml"
# ---------------------------------------------------------------------------

LLM = None
_llm_lock = threading.Lock()  # llama_cpp Llama objects are NOT thread-safe.

MODEL_PATH = os.environ.get("LLAMA_MODEL_PATH", "")
PROMPT_TEMPLATE = os.environ.get("LLAMA_PROMPT_TEMPLATE", "mistral").lower()

try:
    if MODEL_PATH and os.path.exists(MODEL_PATH):
        from llama_cpp import Llama
        LLM = Llama(
            model_path=MODEL_PATH,
            n_gpu_layers=-1,  # Use all GPU layers when available
            n_ctx=2048,
            verbose=False,
        )
        logger.info(f"Loaded LLaMA model from {MODEL_PATH!r} (template: {PROMPT_TEMPLATE!r})")
    else:
        logger.warning(
            "LLAMA_MODEL_PATH not set or file not found. Running in MOCK mode. "
            "Set LLAMA_MODEL_PATH to a GGUF model file to enable real inference."
        )
except ImportError:
    logger.warning("llama-cpp-python not installed. Running in MOCK mode.")
except Exception as e:
    logger.error(f"Failed to load LLaMA model: {e}. Running in MOCK mode.")


# ---------------------------------------------------------------------------
# Prompt formatting — each model family uses a different chat template
# ---------------------------------------------------------------------------

def _format_prompt(user_prompt: str) -> str:
    """Wrap the user prompt in the correct chat template for the loaded model."""
    if PROMPT_TEMPLATE == "llama3":
        # Llama 3 instruct format
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
    elif PROMPT_TEMPLATE == "chatml":
        # ChatML format (used by Mistral Nemo, Qwen, etc.)
        return (
            "<|im_start|>system\n"
            f"{SYSTEM_PROMPT}<|im_end|>\n"
            "<|im_start|>user\n"
            f"{user_prompt}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
    else:
        # Mistral / Zephyr instruct format (default)
        return (
            f"<|system|>\n{SYSTEM_PROMPT}</s>\n"
            f"<|user|>\n{user_prompt}</s>\n"
            "<|assistant|>\n"
        )


def _extract_json_array(text: str) -> str:
    """Extract the first valid JSON array from LLM output, stripping markdown fences."""
    # Try to extract a JSON array directly via regex (most reliable)
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        return match.group(0)
    # Fallback: strip markdown fences if present
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/rank-tasks", response_model=List[RankedTask])
async def rank_tasks(req: RankRequest):
    if not req.tasks:
        return []

    if len(req.tasks) == 1:
        return [RankedTask(task_id=req.tasks[0].task_id, score_delta=0.0, reason="Only one candidate")]

    if LLM is None:
        # Mock mode: shuffle deltas randomly so callers can actually test the
        # tie-breaking path end-to-end without a real model loaded.
        deltas = [round(random.uniform(-0.10, 0.10), 4) for _ in req.tasks]
        return [
            RankedTask(task_id=t.task_id, score_delta=d, reason="Mock inference (no model loaded)")
            for t, d in zip(req.tasks, deltas)
        ]

    user_prompt = build_prompt(req.worker_caps, [t.model_dump() for t in req.tasks])
    full_prompt = _format_prompt(user_prompt)

    # output_text is declared here so it is always bound, even if LLM() raises.
    output_text = ""

    try:
        # Acquire the lock — llama_cpp is not thread-safe.
        with _llm_lock:
            response = LLM(
                full_prompt,
                max_tokens=512,
                temperature=0.1,  # Low temperature for deterministic, structured output
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

        # Ensure every input task has an entry; add missing ones with a zero delta.
        scored_ids = {t.task_id for t in ranked_tasks}
        for t in req.tasks:
            if t.task_id not in scored_ids:
                logger.warning(f"AI omitted task {t.task_id!r} from ranking; appending with delta=0.")
                ranked_tasks.append(
                    RankedTask(task_id=t.task_id, score_delta=0.0, reason="Missed by AI — zero delta applied")
                )

        return ranked_tasks

    except json.JSONDecodeError as e:
        logger.error(
            f"Failed to parse LLM JSON output: {e}\n"
            f"Raw output was: {output_text!r}"
        )
        return [
            RankedTask(task_id=t.task_id, score_delta=0.0, reason="LLM output parsing failed")
            for t in req.tasks
        ]
    except Exception as e:
        logger.exception(f"LLM inference failed: {e}")
        raise HTTPException(status_code=500, detail="Inference failed")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": LLM is not None,
        "prompt_template": PROMPT_TEMPLATE,
        "model_path": MODEL_PATH or None,
    }
