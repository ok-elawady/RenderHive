"""Base adapter contracts."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from core.dcc_discovery import DCCInstallation
from core.task_normalizer import TaskContext


class AdapterError(RuntimeError):
    pass


@dataclass
class ExecutionPlan:
    command: List[str]
    cwd: str
    env: Dict[str, str] = field(default_factory=dict)
    dcc: str = ""
    version: str = ""
    executable: str = ""
    description: str = ""


def split_command(command: str) -> List[str]:
    if not str(command or "").strip():
        return []
    try:
        return shlex.split(command, posix=True)
    except ValueError as error:
        raise AdapterError("Invalid task command: {}".format(error))


def replace_tokens(command: str, replacements: Dict[str, str]) -> str:
    result = str(command or "")
    for token, value in replacements.items():
        for variant in (token.upper(), token.lower()):
            result = result.replace("{" + variant + "}", str(value))
    return result


def scene_cwd(task: TaskContext) -> str:
    candidates = [task.project_path, os.path.dirname(task.scene_path), os.getcwd()]
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return os.getcwd()


class BaseAdapter:
    dcc = ""

    def __init__(self, installations: Sequence[DCCInstallation]):
        self.installations = list(installations)

    def build_plan(self, task: TaskContext) -> ExecutionPlan:
        raise NotImplementedError
