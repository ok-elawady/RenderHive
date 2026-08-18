from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs"
sys.path.insert(0, str(ROOT))

from renderhive_houdini.core.scene_context import SceneContext
from renderhive_houdini.adapters.render_node_registry import RenderNodeInfo
from renderhive_houdini.validation.validator import validate


def context(tmp_path, saved=True):
    project = tmp_path / "show"
    shot = project / "shot"
    shot.mkdir(parents=True)
    hip = shot / "scene.hip"
    if saved:
        hip.write_text("test", encoding="utf-8")
    return SceneContext(
        hip_path=str(hip) if saved else "",
        hip_name="scene.hip" if saved else "Untitled.hip",
        houdini_version="20.5.278",
        frame_start=1,
        frame_end=24,
        current_frame=1,
        fps=24,
        hip_directory=str(shot),
        job_directory=str(project),
        is_new_file=not saved,
        has_unsaved_changes=False,
        project_path=str(project),
    )


def node(tmp_path, output=True):
    output_path = tmp_path / "show" / "render" / "a.$F4.exr"
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
        output_path=str(output_path) if output else "",
        resolution_width=1920,
        resolution_height=1080,
        is_bypassed=False,
        is_locked=False,
        is_renderable=True,
    )


def test_valid_scene_has_no_errors(tmp_path):
    results = validate(context(tmp_path), node(tmp_path))
    assert not [item for item in results if item.severity == "ERROR"]


def test_unsaved_scene_and_missing_output_block_submission(tmp_path):
    results = validate(context(tmp_path, saved=False), node(tmp_path, output=False))
    messages = [item.message for item in results if item.severity == "ERROR"]
    assert any("Save the HIP" in message for message in messages)
    assert any("no final image output" in message.lower() for message in messages)
