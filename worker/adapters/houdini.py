"""Houdini execution adapter supporting every detected Houdini version.

HIP jobs are always opened through the selected Houdini installation's
``hython.exe``.  A USD Render ROP may report its execution mode as ``husk``,
but the intermediate USD normally does not exist until the HIP file and ROP
are evaluated.  In that case hython executes the selected node and the node
launches husk internally.

Direct ``husk.exe`` execution is reserved for standalone, already-existing USD
files.  This avoids trying to launch the submitter's hython preview command as
if it were a husk command.
"""

from __future__ import annotations

import os
import re
from typing import List

from core.dcc_discovery import select_installation
from core.runtime_paths import bundled_path
from core.task_normalizer import TaskContext

from .base import AdapterError, BaseAdapter, ExecutionPlan, scene_cwd, split_command


_USD_EXTENSIONS = (".usd", ".usda", ".usdc", ".usdz")
_HIP_EXTENSIONS = (".hip", ".hiplc", ".hipnc")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _clean_path(value: str) -> str:
    return os.path.normpath(os.path.expanduser(os.path.expandvars(str(value or "").strip())))


def _is_absolute_path(value: str) -> bool:
    text = str(value or "").strip()
    return bool(os.path.isabs(text) or _WINDOWS_ABSOLUTE_RE.match(text) or text.startswith(("\\\\", "//")))


def _resolve_task_path(value: str, task: TaskContext) -> str:
    path = _clean_path(value)
    if not path:
        return ""
    if _is_absolute_path(path):
        return path

    bases = [
        task.project_path,
        os.path.dirname(task.scene_path or ""),
        os.getcwd(),
    ]
    for base in bases:
        if not base:
            continue
        candidate = os.path.normpath(os.path.join(base, path))
        if os.path.isfile(candidate):
            return candidate
    return os.path.normpath(os.path.join(bases[-1], path))


def _looks_like_hip_job(task: TaskContext) -> bool:
    extension = os.path.splitext(str(task.scene_path or ""))[1].lower()
    return extension in _HIP_EXTENSIONS or bool(task.scene_path and task.render_node)


def _build_tokenized_husk_command(command_text: str, husk_exe: str, task: TaskContext) -> List[str]:
    """Parse only commands that explicitly target husk.

    Placeholders are replaced with no-space sentinels before tokenization so an
    unquoted ``{HUSK_EXEC}`` cannot be broken at ``Program Files``.
    """

    original = str(command_text or "").strip()
    if not original:
        return []

    sentinels = {
        "HUSK_EXEC": "__RENDERHIVE_HUSK_EXEC__",
        "SCENE_PATH": "__RENDERHIVE_SCENE_PATH__",
        "USD_PATH": "__RENDERHIVE_USD_PATH__",
        "START_FRAME": "__RENDERHIVE_START_FRAME__",
        "END_FRAME": "__RENDERHIVE_END_FRAME__",
        "FRAME": "__RENDERHIVE_FRAME__",
        "FRAME_STEP": "__RENDERHIVE_FRAME_STEP__",
        "RENDERER": "__RENDERHIVE_RENDERER__",
        "OUTPUT_PATH": "__RENDERHIVE_OUTPUT_PATH__",
    }
    prepared = original
    for token, sentinel in sentinels.items():
        prepared = prepared.replace("{" + token + "}", sentinel)
        prepared = prepared.replace("{" + token.lower() + "}", sentinel)

    command = split_command(prepared)
    if not command:
        return []

    first = command[0].strip('"')
    first_name = os.path.basename(first).lower()
    explicitly_husk = (
        first == sentinels["HUSK_EXEC"]
        or first_name in ("husk", "husk.exe")
        or os.path.normcase(first) == os.path.normcase(husk_exe)
    )
    if not explicitly_husk:
        return []

    replacements = {
        sentinels["HUSK_EXEC"]: husk_exe,
        sentinels["SCENE_PATH"]: task.scene_path,
        sentinels["USD_PATH"]: task.usd_output_path,
        sentinels["START_FRAME"]: str(task.frame_start),
        sentinels["END_FRAME"]: str(task.frame_end),
        sentinels["FRAME"]: str(task.frame_start),
        sentinels["FRAME_STEP"]: str(task.frame_step),
        sentinels["RENDERER"]: task.renderer,
        sentinels["OUTPUT_PATH"]: task.output_path,
    }
    resolved: List[str] = []
    for argument in command:
        value = argument
        for sentinel, replacement in replacements.items():
            value = value.replace(sentinel, str(replacement or ""))
        resolved.append(value)

    resolved[0] = husk_exe
    return resolved


class HoudiniAdapter(BaseAdapter):
    dcc = "houdini"

    def _build_hython_rop(self, task: TaskContext, hython_exe: str) -> List[str]:
        if not task.scene_path:
            raise AdapterError("The Houdini task does not include a HIP file path.")
        if not task.render_node:
            raise AdapterError("The Houdini task does not include a render node path.")

        script = bundled_path("render_scripts", "houdini_render_rop.py")
        if not os.path.isfile(script):
            raise AdapterError("Bundled Houdini render script is missing: {}".format(script))

        command = [
            hython_exe,
            script,
            "--scene",
            task.scene_path,
            "--node",
            task.render_node,
            "--start",
            str(task.frame_start),
            "--end",
            str(task.frame_end),
            "--step",
            str(task.frame_step),
        ]
        if task.camera_override and task.camera:
            command.extend(["--camera", task.camera])
        if task.renderer_override and task.renderer:
            command.extend(["--renderer", task.renderer])
        if task.output_override and task.output_path:
            command.extend(["--output", task.output_path])
        if task.resolution_override:
            if task.resolution_width > 0:
                command.extend(["--width", str(task.resolution_width)])
            if task.resolution_height > 0:
                command.extend(["--height", str(task.resolution_height)])
        return command

    def _build_husk(self, task: TaskContext, husk_exe: str, usd_path: str) -> List[str]:
        if not usd_path:
            raise AdapterError("Direct husk execution requires a USD file path.")
        if not os.path.isfile(usd_path):
            raise AdapterError(
                "Direct husk input does not exist: {}. Submit the HIP render node so hython can generate the intermediate USD first.".format(
                    usd_path
                )
            )

        custom = _build_tokenized_husk_command(task.command, husk_exe, task)
        if custom:
            # Replace the original possibly-relative token with the verified path.
            custom = [usd_path if item == task.usd_output_path else item for item in custom]
            return custom

        command = [husk_exe, usd_path, "--frame", str(task.frame_start)]
        if task.renderer:
            command.extend(["--renderer", task.renderer])
        return command

    def build_plan(self, task: TaskContext) -> ExecutionPlan:
        installation = select_installation(self.installations, task.dcc_version)
        if installation is None:
            requested = task.dcc_version or "any installed version"
            available = ", ".join(item.version for item in self.installations) or "none"
            raise AdapterError(
                "Houdini {} is not installed. Available Houdini versions: {}.".format(requested, available)
            )

        hython_exe = installation.executables.get("hython") or ""
        husk_exe = installation.executables.get("husk") or ""
        requested_mode = str(task.execution_mode or "hython").lower()
        hip_job = _looks_like_hip_job(task)

        # A USD Render ROP inside a HIP file must be evaluated before its
        # intermediate USD exists.  Run the selected node through hython; that
        # node invokes husk itself using the scene's real render settings.
        if hip_job:
            if not hython_exe:
                raise AdapterError("hython.exe was not found for Houdini {}.".format(installation.version))
            command = self._build_hython_rop(task, hython_exe)
            executable = hython_exe
            if "husk" in requested_mode:
                resolved_mode = "hython USD ROP (invokes husk)"
            else:
                resolved_mode = "hython"
        elif "husk" in requested_mode:
            if not husk_exe:
                raise AdapterError("husk.exe was not found for Houdini {}.".format(installation.version))
            usd_path = _resolve_task_path(task.usd_output_path or task.scene_path, task)
            command = self._build_husk(task, husk_exe, usd_path)
            executable = husk_exe
            resolved_mode = "direct husk"
        else:
            if not hython_exe:
                raise AdapterError("hython.exe was not found for Houdini {}.".format(installation.version))
            command = self._build_hython_rop(task, hython_exe)
            executable = hython_exe
            resolved_mode = "hython"

        env = dict(task.env)
        env["RENDERHIVE_DCC"] = "houdini"
        env["RENDERHIVE_HOUDINI_VERSION"] = installation.version
        env["RENDERHIVE_REQUESTED_EXECUTION_MODE"] = requested_mode
        env.setdefault("HIP", os.path.dirname(task.scene_path))
        if task.project_path:
            env.setdefault("JOB", task.project_path)

        return ExecutionPlan(
            command=command,
            cwd=scene_cwd(task),
            env=env,
            dcc="houdini",
            version=installation.version,
            executable=executable,
            description="Houdini {} {} render".format(installation.version, resolved_mode),
        )
