"""Normalize legacy and current RenderHive task payloads."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class TaskContext:
    task_id: str
    dcc: str
    dcc_version: str
    command: str
    scene_path: str
    project_path: str
    output_path: str
    frame_start: int
    frame_end: int
    frame_step: int
    renderer: str
    render_node: str
    camera: str
    execution_mode: str
    usd_output_path: str
    camera_override: bool
    renderer_override: bool
    output_override: bool
    resolution_override: bool
    resolution_width: int
    resolution_height: int
    env: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _integer(*values: Any, default: int = 0) -> int:
    for value in values:
        try:
            return int(round(float(value)))
        except Exception:
            continue
    return int(default)



def _boolean(*values: Any, default: bool = False) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "on", "enabled"):
            return True
        if text in ("0", "false", "no", "off", "disabled", ""):
            return False
    return bool(default)

def _env_dict(*values: Any) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            if key is None or item is None:
                continue
            result[str(key)] = str(item)
    return result


def _detect_dcc(explicit: str, command: str, scene_path: str) -> str:
    value = str(explicit or "").strip().lower()
    if value in ("maya", "houdini"):
        return value

    haystack = "{} {}".format(command or "", scene_path or "").lower()
    if any(token in haystack for token in ("hython", "husk", "hbatch", ".hip", "renderhive_houdini")):
        return "houdini"
    return "maya"


def normalize_task(task: Dict[str, Any]) -> TaskContext:
    if not isinstance(task, dict):
        raise ValueError("Task payload must be a dictionary.")

    layer = _dict(task.get("layer"))
    job = _dict(task.get("job"))
    scene_info = _dict(task.get("scene_info"))
    if not scene_info:
        scene_info = _dict(layer.get("scene_info"))
    execution = _dict(task.get("execution"))
    if not execution:
        execution = _dict(scene_info.get("execution"))
    frames = _dict(task.get("frames"))
    if not frames:
        frames = _dict(layer.get("frames"))
    resolution = _dict(task.get("resolution"))
    if not resolution:
        resolution = _dict(scene_info.get("resolution"))
    if not resolution:
        resolution = _dict(execution.get("resolution"))

    command = _text(task.get("command"), layer.get("command"))
    scene_path = _text(
        task.get("scene_path"),
        layer.get("scene_path"),
        scene_info.get("scene_path"),
        scene_info.get("hip_file"),
        scene_info.get("hip_path"),
    )
    project_path = _text(
        task.get("project_path"),
        scene_info.get("project_path"),
        task.get("project"),
        job.get("project_path"),
    )
    output_path = _text(
        task.get("output_path"),
        scene_info.get("output_path"),
        execution.get("output_path"),
    )

    explicit_dcc = _text(task.get("dcc"), scene_info.get("dcc"), layer.get("dcc"))
    dcc = _detect_dcc(explicit_dcc, command, scene_path)

    dcc_version = _text(
        task.get("dcc_version"),
        scene_info.get("dcc_version"),
        scene_info.get("houdini_version") if dcc == "houdini" else scene_info.get("maya_version"),
        task.get("houdini_version") if dcc == "houdini" else task.get("maya_version"),
        os.environ.get("RENDERHIVE_{}_VERSION".format(dcc.upper())),
    )

    frame_start = _integer(
        task.get("frame_start"),
        frames.get("start"),
        task.get("start_frame"),
        default=1,
    )
    frame_end = _integer(
        task.get("frame_end"),
        frames.get("end"),
        task.get("end_frame"),
        default=frame_start,
    )
    frame_step = max(
        1,
        _integer(task.get("frame_step"), frames.get("step"), default=1),
    )

    task_id = _text(task.get("id"), task.get("task_id"), task.get("frame_id"), "unknown")
    renderer = _text(task.get("renderer"), scene_info.get("renderer"), execution.get("renderer"))
    render_node = _text(task.get("render_node"), scene_info.get("render_node"), execution.get("render_node"))
    camera = _text(task.get("camera"), scene_info.get("camera"), execution.get("camera"))
    execution_mode = _text(
        task.get("execution_mode"),
        execution.get("mode"),
        execution.get("worker_mode"),
        "hython" if dcc == "houdini" else "render",
    ).lower()
    usd_output_path = _text(
        task.get("usd_output_path"),
        execution.get("usd_output_path"),
        scene_info.get("usd_output_path"),
    )
    camera_override = _boolean(task.get("camera_override"), execution.get("camera_override"))
    renderer_override = _boolean(task.get("renderer_override"), execution.get("renderer_override"))
    output_override = _boolean(task.get("output_override"), execution.get("output_override"))
    resolution_override = _boolean(task.get("resolution_override"), execution.get("resolution_override"))
    resolution_width = _integer(
        task.get("resolution_width"),
        resolution.get("width"),
        execution.get("width"),
        default=0,
    )
    resolution_height = _integer(
        task.get("resolution_height"),
        resolution.get("height"),
        execution.get("height"),
        default=0,
    )

    env = _env_dict(layer.get("env"), task.get("env"), execution.get("env"))

    return TaskContext(
        task_id=task_id,
        dcc=dcc,
        dcc_version=dcc_version,
        command=command,
        scene_path=scene_path,
        project_path=project_path,
        output_path=output_path,
        frame_start=frame_start,
        frame_end=frame_end,
        frame_step=frame_step,
        renderer=renderer,
        render_node=render_node,
        camera=camera,
        execution_mode=execution_mode,
        usd_output_path=usd_output_path,
        camera_override=camera_override,
        renderer_override=renderer_override,
        output_override=output_override,
        resolution_override=resolution_override,
        resolution_width=resolution_width,
        resolution_height=resolution_height,
        env=env,
        raw=task,
    )
