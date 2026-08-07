"""Maya execution adapter supporting every detected Maya version."""

from __future__ import annotations

import os
from typing import List

from core.dcc_discovery import select_installation
from core.task_normalizer import TaskContext

from .base import AdapterError, BaseAdapter, ExecutionPlan, replace_tokens, scene_cwd, split_command


class MayaAdapter(BaseAdapter):
    dcc = "maya"

    def build_plan(self, task: TaskContext) -> ExecutionPlan:
        installation = select_installation(self.installations, task.dcc_version)
        if installation is None:
            requested = task.dcc_version or "any installed version"
            available = ", ".join(item.version for item in self.installations) or "none"
            raise AdapterError(
                "Maya {} is not installed. Available Maya versions: {}.".format(requested, available)
            )

        render_exe = installation.executables.get("render") or ""
        mayapy_exe = installation.executables.get("mayapy") or ""
        if not render_exe:
            raise AdapterError("Render.exe was not found for Maya {}.".format(installation.version))
        if not task.scene_path:
            raise AdapterError("The Maya task does not include a scene path.")

        replacements = {
            "MAYA_EXEC": render_exe,
            "MAYA_RENDER_EXEC": render_exe,
            "MAYAPY_EXEC": mayapy_exe,
            "SCENE_PATH": task.scene_path,
            "PROJECT_PATH": task.project_path,
            "OUTPUT_PATH": task.output_path,
            "START_FRAME": str(task.frame_start),
            "END_FRAME": str(task.frame_end),
            "FRAME": str(task.frame_start),
            "FRAME_STEP": str(task.frame_step),
            "RENDERER": task.renderer,
            "CAMERA": task.camera,
        }

        if task.command:
            command_text = replace_tokens(task.command, replacements)
            command = split_command(command_text)
            if not command:
                raise AdapterError("The Maya task command is empty.")
            first_name = os.path.basename(command[0]).lower()
            if first_name in ("render", "render.exe"):
                command[0] = render_exe
        else:
            command = [
                render_exe,
                "-s",
                str(task.frame_start),
                "-e",
                str(task.frame_end),
                "-b",
                str(task.frame_step),
            ]
            if task.renderer:
                command.extend(["-r", task.renderer])
            if task.project_path:
                command.extend(["-proj", task.project_path])
            if task.camera:
                command.extend(["-cam", task.camera])
            command.append(task.scene_path)

        env = dict(task.env)
        env["RENDERHIVE_DCC"] = "maya"
        env["RENDERHIVE_MAYA_VERSION"] = installation.version

        return ExecutionPlan(
            command=command,
            cwd=scene_cwd(task),
            env=env,
            dcc="maya",
            version=installation.version,
            executable=render_exe,
            description="Maya {} render".format(installation.version),
        )
