from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs"
sys.path.insert(0, str(ROOT))

from renderhive_houdini.api.models import normalize_worker
from renderhive_houdini.adapters.render_node_registry import RenderNodeInfo
from renderhive_houdini.core.scene_context import SceneContext
from renderhive_houdini.core.task_builder import build_task, build_worker_command
from renderhive_houdini.api.config import normalize_config


def context():
    return SceneContext(
        hip_path="P:/show/shot/scene.hip",
        hip_name="scene.hip",
        houdini_version="20.5.278",
        frame_start=1,
        frame_end=10,
        current_frame=1,
        fps=24,
        hip_directory="P:/show/shot",
        job_directory="P:/show",
        is_new_file=False,
        has_unsaved_changes=False,
        scene_name="scene",
        project_name="show",
        project_path="P:/show",
        output_root="P:/show/render",
    )


def node():
    return RenderNodeInfo(
        path="/stage/usdrender_rop1",
        name="usdrender_rop1",
        type_name="usdrender_rop",
        type_label="USD Render ROP",
        category="Lop",
        renderer="Karma XPU",
        execution_mode="husk",
        frame_start=1,
        frame_end=10,
        frame_step=1,
        frame_source="Render Node",
        camera="/cameras/cam1",
        output_path="P:/show/render/beauty.$F4.exr",
        resolution_width=1920,
        resolution_height=1080,
        is_bypassed=False,
        is_locked=False,
        is_renderable=True,
        available_cameras=("/cameras/cam1", "/cameras/cam2"),
        available_renderers=("Karma CPU", "Karma XPU"),
        usd_output_path="P:/show/usd/render.usd",
        output_source="usd_render_product",
        camera_override=True,
        renderer_override=True,
        output_override=True,
        resolution_override=True,
    )


def test_worker_details_are_preserved_for_pool_dialog():
    worker = normalize_worker({
        "id": 7,
        "hostname": "render-07",
        "ip_address": "10.0.0.7",
        "status": "ONLINE",
        "cores": 32,
        "memory_mb": 65536,
        "gpu_models": ["RTX 4090"],
        "system_info": {"gpu_utilization": 20},
        "pools": [{"id": "pool", "name": "Houdini"}],
    })
    assert worker["ip_address"] == "10.0.0.7"
    assert worker["system_info"]["gpu_utilization"] == 20
    assert worker["pools"][0]["id"] == "pool"


def test_override_command_contains_only_requested_job_overrides():
    task = build_task(
        context(),
        node(),
        job_name="shot010",
        project_name="show",
    )
    command = build_worker_command(task, normalize_config({}))
    assert '--camera "/cameras/cam1"' in command
    assert '--renderer "Karma XPU"' in command
    assert '--output "P:\\show\\render\\beauty.$F4.exr"' in command
    assert "--width 1920" in command
    assert "--height 1080" in command


def test_usd_intermediate_path_is_kept_separate_from_final_image_output():
    task = build_task(
        context(),
        node(),
        job_name="shot010",
        project_name="show",
    )
    assert task["output_path"].lower().endswith("beauty.$f4.exr")
    assert task["execution"]["usd_output_path"].lower().endswith("render.usd")
