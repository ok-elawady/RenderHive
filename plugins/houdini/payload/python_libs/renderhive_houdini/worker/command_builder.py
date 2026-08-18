"""Backward-compatible command builder for worker handoff."""

from __future__ import absolute_import

from renderhive_houdini.core.task_builder import build_worker_command


def build(task, config):
    return build_worker_command(task, config)
