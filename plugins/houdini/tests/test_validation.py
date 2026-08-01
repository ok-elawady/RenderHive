from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs"
sys.path.insert(0, str(ROOT))

from renderhive_houdini.core.scene_context import SceneContext
from renderhive_houdini.adapters.render_node_registry import RenderNodeInfo
from renderhive_houdini.validation.validator import validate


def context(saved=True):
    return SceneContext(
        hip_path="P:/show/shot/scene.hip" if saved else "",
        hip_name="scene.hip" if saved else "Untitled.hip",
        houdini_version="20.5.278",
        frame_start=1,
        frame_end=24,
        current_frame=1,
        fps=24,
        hip_directory="P:/show/shot",
        job_directory="P:/show",
        is_new_file=not saved,
        has_unsaved_changes=False,
    )


def node(output=True):
    return RenderNodeInfo(
        path="/out/arnold1",
        name="arnold1",
        type_name="arnold",
        type_label="Arnold ROP",
        category="Driver",
        renderer="Arnold",
        execution_mode="hython",
        frame_start=1,
        frame_end=24,
        frame_step=1,
        frame_source="Render Node",
        camera="/obj/cam1",
        output_path="P:/show/render/a.$F4.exr" if output else "",
        resolution_width=1920,
        resolution_height=1080,
        is_bypassed=False,
        is_locked=False,
        is_renderable=True,
    )


def test_valid_scene_has_no_errors():
    results = validate(context(), node())
    assert not [item for item in results if item.severity == "ERROR"]


def test_unsaved_scene_and_missing_output_block_submission():
    results = validate(context(saved=False), node(output=False))
    messages = [item.message for item in results if item.severity == "ERROR"]
    assert any("Save the HIP" in message for message in messages)
    assert any("no output path" in message.lower() for message in messages)
