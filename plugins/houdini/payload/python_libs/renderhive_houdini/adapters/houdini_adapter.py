"""High-level Houdini Object Model adapter."""

from __future__ import absolute_import

from renderhive_houdini.adapters.render_node_registry import (
    discover_render_nodes,
    node_info_from_path,
    selected_render_node,
)
from renderhive_houdini.core.scene_context import read_scene_context


class HoudiniAdapter(object):
    """Read-only bridge between the submitter UI and Houdini."""

    def scene_context(self):
        return read_scene_context()

    def render_nodes(self):
        return discover_render_nodes()

    def selected_render_node(self):
        return selected_render_node()

    def render_node(self, path):
        return node_info_from_path(path)
