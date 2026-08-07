SYSTEM_PROMPT = """You are an AI task scheduler for a distributed rendering farm.
Your job is to act as a tie-breaker for rendering tasks that have very similar base scores.
Given a worker node's current hardware capabilities and a list of candidate tasks, evaluate how well each task fits the worker.
Return a JSON array of task IDs sorted by best fit first, with a reasoning string for each.

Consider these rules:
1. High-resolution rendering and GPU renderers (like Redshift or Karma XPU) benefit from workers with lots of VRAM and available system RAM.
2. If a worker is nearly fully utilized, lightweight tasks (like utility scripts or compositing) might be a safer choice than heavy 3D renders.
3. Your output must be strictly valid JSON matching this schema:
[
  {
    "task_id": "uuid-string",
    "score_delta": 0.0,
    "reason": "Brief explanation"
  }
]
Where score_delta is a float between -0.20 and +0.20 that nudges the base score.
Positive values make the task more likely to be dispatched to this worker.
Negative values make it less likely. Do not exceed \u00b10.20.
"""

import json

def build_prompt(worker_caps: dict, tasks: list) -> str:
    # Use json.dumps so the LLM receives valid JSON, not Python repr strings.
    worker_caps_json = json.dumps(worker_caps, indent=2, default=str)
    prompt = f"Worker Capabilities:\n{worker_caps_json}\n\nCandidate Tasks:\n"
    for t in tasks:
        scene_info_json = json.dumps(t.get("scene_info", {}), default=str)
        prompt += f"- Task ID: {t['task_id']}\n"
        prompt += f"  Priority: {t['priority']}\n"
        prompt += f"  Base Score: {t['base_score']:.4f}\n"
        prompt += f"  Scene Info: {scene_info_json}\n"

    prompt += "\nOutput ONLY the JSON array. Do not include markdown formatting."
    return prompt
