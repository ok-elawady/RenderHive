from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs"
sys.path.insert(0, str(ROOT))

from renderhive_houdini.core.scene_context import SceneContext
from renderhive_houdini.adapters.render_node_registry import RenderNodeInfo
from renderhive_houdini.core.task_builder import build_preview


def test_preview_payload_contains_houdini_execution_data():
    context = SceneContext(
        hip_path="P:/show/scene.hip",
        hip_name="scene.hip",
        houdini_version="21.0.440",
        frame_start=1,
        frame_end=10,
        current_frame=1,
        fps=24,
        hip_directory="P:/show",
        job_directory="P:/show",
        is_new_file=False,
        has_unsaved_changes=False,
    )
    node = RenderNodeInfo(
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
        output_path="P:/show/render/a.$F4.exr",
        resolution_width=1920,
        resolution_height=1080,
        is_bypassed=False,
        is_locked=False,
        is_renderable=True,
    )
    payload = build_preview(context, node, "shot010", chunk_size=2)
    assert payload["dcc"] == "houdini"
    assert payload["render_node"] == "/stage/usdrender_rop1"
    assert payload["execution"]["mode"] == "husk"
    assert payload["frames"]["chunk_size"] == 2
