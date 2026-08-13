import json

SYSTEM_PROMPT = """You are an AI task scheduler for a distributed rendering farm.
Your job is to act as a tie-breaker for rendering tasks that have very similar base scores.
Given a worker node's current hardware capabilities and a list of candidate tasks, evaluate how well each task fits the worker.

Consider these rules:
1. High-resolution rendering and GPU renderers (like Redshift or Karma XPU) benefit from workers with lots of VRAM and available system RAM.
2. If a worker is nearly fully utilized, lightweight tasks (like utility scripts or compositing) might be a safer choice than heavy 3D renders.
3. Tasks with more retries indicate instability — prefer them on the most capable worker to maximize the chance of success.
4. You MUST assign a non-zero score_delta (e.g. +0.15 or -0.15) based on your reasoning. Never return exactly 0.0 unless completely unsure.
5. Evaluate each task EXACTLY ONCE. After listing the tasks provided, terminate the JSON array immediately and do not generate any further text or duplicate entries.
6. Your output must be strictly valid JSON matching this schema:
[
  {
    "task_id": "uuid-string",
    "score_delta": 0.15,
    "reason": "Brief explanation"
  }
]
Where score_delta is a float between -0.20 and +0.20 that nudges the base score.
Positive values make the task more likely to be dispatched to this worker.
Negative values make it less likely. Do not exceed ±0.20.
Output ONLY the JSON array. Do not include markdown formatting or any other text.
"""

# Fields from scene_info that are useful for AI reasoning.
# Omitting verbose fields like file paths prevents context window overflow.
_SCENE_INFO_ALLOW = {
    "renderer",
    "dcc",
    "dcc_version",
    "resolution",
    "camera",
    "render_node",
    "execution_mode",
    "houdini_version",
    "maya_version",
}


def _trim_scene_info(scene_info: dict) -> dict:
    """Return a trimmed copy of scene_info with only AI-relevant fields.

    Strips file paths, environment dumps, and other verbose data that would
    bloat the prompt and potentially overflow the context window.
    """
    return {k: v for k, v in scene_info.items() if k in _SCENE_INFO_ALLOW}


def build_prompt(worker_caps: dict, tasks: list) -> str:
    """Build the user-turn prompt for the AI ranking request."""
    # Use json.dumps so the LLM receives valid JSON, not Python repr strings.
    worker_caps_json = json.dumps(worker_caps, indent=2, default=str)
    prompt = f"Worker Capabilities:\n{worker_caps_json}\n\nCandidate Tasks:\n"
    for t in tasks:
        trimmed_scene_info = _trim_scene_info(t.get("scene_info", {}))
        scene_info_json = json.dumps(trimmed_scene_info, default=str)
        prompt += f"- Task ID: {t['task_id']}\n"
        prompt += f"  Priority: {t['priority']}\n"
        prompt += f"  Base Score: {t['base_score']:.4f}\n"
        prompt += f"  Scene Info: {scene_info_json}\n"

    prompt += "\nOutput ONLY the JSON array. Do not include markdown formatting."
    return prompt
