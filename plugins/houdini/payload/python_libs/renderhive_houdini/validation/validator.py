"""Validation orchestration."""

from __future__ import absolute_import

from renderhive_houdini.validation import scene_checks, render_checks


def validate(context, node_info):
    results = []
    results.extend(scene_checks.run(context))
    results.extend(render_checks.run(node_info))
    return results
