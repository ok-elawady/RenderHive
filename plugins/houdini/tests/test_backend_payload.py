from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs"
sys.path.insert(0, str(ROOT))

from renderhive_houdini.core.scene_context import SceneContext
from renderhive_houdini.adapters.render_node_registry import RenderNodeInfo
from renderhive_houdini.core.task_builder import build_task, build_api_request
from renderhive_houdini.api.config import normalize_config


def test_houdini_job_matches_job_create_contract():
    context = SceneContext(
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
    node = RenderNodeInfo(
        path="/out/arnold1",
        name="arnold1",
        type_name="arnold",
        type_label="Arnold ROP",
        category="Driver",
        renderer="Arnold",
        execution_mode="hython",
        frame_start=1,
        frame_end=10,
        frame_step=1,
        frame_source="Render Node",
        camera="/obj/cam1",
        output_path="P:/show/render/beauty.$F4.exr",
        resolution_width=1920,
        resolution_height=1080,
        is_bypassed=False,
        is_locked=False,
        is_renderable=True,
    )
    task = build_task(
        context,
        node,
        job_name="shot010",
        project_name="show",
        chunk_size=2,
        pool_targeting={
            "strategy": "selected_only",
            "selected_pool_ids": ["11111111-1111-4111-8111-111111111111"],
            "effective_pool_ids": ["11111111-1111-4111-8111-111111111111"],
            "effective_pool_names": ["Houdini"],
        },
    )
    payload = build_api_request(task, normalize_config({}))
    assert payload["project"] == "show"
    assert payload["visible_name"] == "shot010"
    assert payload["layers"][0]["frame_range"] == "1-10"
    assert payload["layers"][0]["chunk_size"] == 2
    assert payload["layers"][0]["scene_info"]["dcc"] == "houdini"
    assert "{frame}" in payload["layers"][0]["command"]
    assert "dcc:houdini" in payload["layers"][0]["tags"]
    assert payload["included_pools"] == ["11111111-1111-4111-8111-111111111111"]
    assert payload["max_tasks_per_worker"] == 1
