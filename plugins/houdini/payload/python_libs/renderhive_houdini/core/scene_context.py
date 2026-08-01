"""Read-only Houdini scene context used by the submitter UI."""

from __future__ import absolute_import

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SceneContext:
    hip_path: str
    hip_name: str
    houdini_version: str
    frame_start: float
    frame_end: float
    current_frame: float
    fps: float
    hip_directory: str
    job_directory: str
    is_new_file: bool
    has_unsaved_changes: bool
    scene_name: str = ""
    project_name: str = ""
    project_path: str = ""
    output_root: str = ""


def _safe_env(hou, name):
    try:
        return str(hou.getenv(name) or "")
    except Exception:
        return ""


def _clean_path(value):
    value = str(value or "").strip()
    if not value:
        return ""
    return os.path.normpath(value)


def _scene_name(hip_name):
    name = os.path.basename(str(hip_name or ""))
    stem, _extension = os.path.splitext(name)
    if stem.lower() in ("", "untitled"):
        return "houdini_job"
    return stem


def _project_context(hip_directory, job_directory):
    project_path = _clean_path(job_directory) or _clean_path(hip_directory)
    project_name = os.path.basename(project_path.rstrip("\\/")) if project_path else "Houdini Project"
    output_root = os.path.join(project_path, "render") if project_path else ""
    return project_name or "Houdini Project", project_path, output_root


def read_scene_context():
    """Return current HIP, project and timeline data without cooking nodes."""
    import hou

    hip_path = str(hou.hipFile.path() or "")
    hip_name = str(hou.hipFile.name() or "Untitled")

    try:
        version = str(hou.applicationVersionString())
    except Exception:
        version_tuple = hou.applicationVersion()
        version = ".".join(str(value) for value in version_tuple)

    try:
        frame_start, frame_end = hou.playbar.frameRange()
    except Exception:
        frame_start, frame_end = (1.0, 240.0)

    try:
        current_frame = float(hou.frame())
    except Exception:
        current_frame = float(frame_start)

    try:
        fps = float(hou.fps())
    except Exception:
        fps = 24.0

    hip_directory = _clean_path(_safe_env(hou, "HIP"))
    job_directory = _clean_path(_safe_env(hou, "JOB"))
    project_name, project_path, output_root = _project_context(
        hip_directory,
        job_directory,
    )

    return SceneContext(
        hip_path=_clean_path(hip_path),
        hip_name=hip_name,
        houdini_version=version,
        frame_start=float(frame_start),
        frame_end=float(frame_end),
        current_frame=current_frame,
        fps=fps,
        hip_directory=hip_directory,
        job_directory=job_directory,
        is_new_file=bool(hou.hipFile.isNewFile()),
        has_unsaved_changes=bool(hou.hipFile.hasUnsavedChanges()),
        scene_name=_scene_name(hip_name),
        project_name=project_name,
        project_path=project_path,
        output_root=_clean_path(output_root),
    )
