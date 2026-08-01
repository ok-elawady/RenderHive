"""Solaris and Karma render adapter metadata."""

from __future__ import absolute_import


def execution_payload(node_info):
    if node_info is None:
        return {}
    return {
        "mode": "husk",
        "render_node": node_info.path,
        "renderer": node_info.renderer,
        "output_path": node_info.output_path,
    }
