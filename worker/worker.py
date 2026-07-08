import json
from pathlib import Path

from adapters.maya_adapter import MayaAdapter


# ============================================================
# PATHS
# ============================================================

WORKER_DIR = Path(__file__).resolve().parent
CONFIG_PATH = WORKER_DIR / "config.json"


# ============================================================
# CONFIG
# ============================================================

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    parent = Path(path).parent
    parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# ============================================================
# TEST TASK
# ============================================================

TEST_TASK = {
    "job_id": 1,
    "task_id": 1,

    "software": "maya",

    "scene_path": r"D:\Moemen\iti\CGTD\RenderHiveProject\Render\scenes\test_scene.ma",
    "project_path": r"D:\Moemen\iti\CGTD\RenderHiveProject\Render",
    "output_path": r"D:\Moemen\iti\CGTD\RenderHiveProject\Render\images",

    "frame_start": 1,
    "frame_end": 5,

    "renderer": "arnold",
    # "renderer": "sw",

    "camera": "renderCam",

    "image_name": "shot01",
    "image_format": "png",
    "frame_padding": 4,

    "width": 1280,
    "height": 720,
}


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
# WORKER SIMULATION
# ============================================================

def run_worker_once():
    """
    دلوقتي دي simulation.
    بعدين هنا هنبدل TEST_TASK بـ task جاي من السيرفر.
    """

    config = load_config()
    task = TEST_TASK

    print("=" * 70)
    print(f"WORKER CLAIMED TASK {task['task_id']} FROM JOB {task['job_id']}")
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

    save_json(config["result_json_path"], result)

    print("=" * 70)
    print("FINAL TASK RESULT")
    print("=" * 70)
    print("Task status:", result["status"].upper())
    print("Result saved to:", config["result_json_path"])

    return result


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_worker_once()
