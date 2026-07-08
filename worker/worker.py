import argparse
import json
from pathlib import Path

from adapters.maya_adapter import MayaAdapter


# ============================================================
# PATHS
# ============================================================

WORKER_DIR = Path(__file__).resolve().parent
CONFIG_PATH = WORKER_DIR / "config.json"

DEFAULT_TASK_PATH = WORKER_DIR / "tasks" / "task_maya_test.json"


# ============================================================
# CONFIG / JSON
# ============================================================

def load_json(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_config():
    return load_json(CONFIG_PATH)


# ============================================================
# ADAPTER SELECTION
# ============================================================

def get_adapter(task, config):
    software = task.get("software", "").lower()

    if software == "maya":
        return MayaAdapter(
            maya_render_exe=config["maya_render_exe"],
            log_folder=config["log_folder"],
        )

    raise ValueError(f"Unsupported software: {software}")


# ============================================================
# VALIDATION
# ============================================================

def validate_task_schema(task):
    required_keys = [
        "job_id",
        "task_id",
        "software",
        "scene_path",
        "project_path",
        "output_path",
        "frame_start",
        "frame_end",
        "camera",
    ]

    missing = []

    for key in required_keys:
        if key not in task:
            missing.append(key)

    if missing:
        raise ValueError(f"Task is missing required keys: {missing}")

    if int(task["frame_start"]) > int(task["frame_end"]):
        raise ValueError("frame_start cannot be greater than frame_end")


# ============================================================
# WORKER
# ============================================================

def run_worker_once(task_path=None, result_path=None):
    config = load_config()

    if task_path is None:
        task_path = DEFAULT_TASK_PATH

    task = load_json(task_path)
    validate_task_schema(task)

    if result_path is None:
        result_path = config["result_json_path"]

    print("=" * 70)
    print("RENDERHIVE WORKER")
    print("=" * 70)
    print("Task file:", task_path)
    print("Result file:", result_path)
    print(f"Claimed task {task['task_id']} from job {task['job_id']}")
    print("=" * 70)

    try:
        adapter = get_adapter(task, config)
        result = adapter.run_task(task)

    except Exception as e:
        result = {
            "job_id": task.get("job_id"),
            "task_id": task.get("task_id"),
            "software": task.get("software"),
            "status": "failed",
            "error": str(e),
        }

    save_json(result_path, result)

    print("=" * 70)
    print("FINAL TASK RESULT")
    print("=" * 70)
    print("Task status:", result["status"].upper())
    print("Result saved to:", result_path)

    return result


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="RenderHive Worker - Local Task Runner"
    )

    parser.add_argument(
        "--task",
        default=str(DEFAULT_TASK_PATH),
        help="Path to task JSON file"
    )

    parser.add_argument(
        "--result",
        default=None,
        help="Path to output result JSON file"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_worker_once(
        task_path=args.task,
        result_path=args.result,
    )
