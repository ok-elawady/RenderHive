"""Select an execution adapter for a normalized task."""

from __future__ import annotations

from typing import Dict, Sequence

from core.dcc_discovery import DCCInstallation
from core.task_normalizer import TaskContext

from .base import AdapterError, BaseAdapter
from .houdini import HoudiniAdapter
from .maya import MayaAdapter


class AdapterFactory:
    def __init__(self, discovered: Dict[str, Sequence[DCCInstallation]]):
        self.discovered = discovered

    def for_task(self, task: TaskContext) -> BaseAdapter:
        if task.dcc == "maya":
            return MayaAdapter(self.discovered.get("maya") or [])
        if task.dcc == "houdini":
            return HoudiniAdapter(self.discovered.get("houdini") or [])
        raise AdapterError("Unsupported DCC: {}".format(task.dcc))
