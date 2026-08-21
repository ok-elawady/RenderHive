"""Render-node, renderer, camera, output and execution validation checks."""

from __future__ import absolute_import

import os
import re

from renderhive_houdini.validation.result import ValidationResult

_FRAME_TOKEN = re.compile(r"(\$F\d*|%0\d+d|#+|<F\d*>)", re.IGNORECASE)
_IMAGE_RENDERERS = ("karma", "arnold", "redshift", "mantra", "renderman", "v-ray", "vray", "octane", "usd render")


def run(node_info):
    if node_info is None:
        return [ValidationResult(
            "ERROR", "Render", "Select an executable ROP or Solaris render node.",
            code="RENDER_NODE_MISSING",
        )]

    results = [ValidationResult(
        "PASSED", "Render", "Render node detected: {}".format(node_info.path),
        node_info.path, code="RENDER_NODE_FOUND",
    )]

    if not node_info.is_renderable:
        results.append(ValidationResult("ERROR", "Render", "The selected node is not executable.", node_info.path, code="RENDER_NODE_NOT_EXECUTABLE"))
    if node_info.is_bypassed:
        results.append(ValidationResult(
            "ERROR", "Render", "The selected render node is bypassed.", node_info.path,
            code="RENDER_NODE_BYPASSED", fixable=True, batch_safe=True,
            data={"node_path": node_info.path},
        ))
    if node_info.is_locked:
        results.append(ValidationResult("INFO", "Render", "The selected render node is inside a locked asset.", node_info.path, code="RENDER_NODE_LOCKED"))

    if node_info.frame_end < node_info.frame_start:
        results.append(ValidationResult("ERROR", "Frames", "Render end frame is before the start frame.", node_info.path, code="FRAME_RANGE_INVALID"))
    elif node_info.frame_step <= 0:
        results.append(ValidationResult(
            "ERROR", "Frames", "Render frame step must be greater than zero.", node_info.path,
            code="FRAME_STEP_INVALID", fixable=True, batch_safe=True,
            data={"node_path": node_info.path},
        ))
    else:
        results.append(ValidationResult("PASSED", "Frames", "Frame range is valid: {}–{} step {}.".format(node_info.frame_start, node_info.frame_end, node_info.frame_step), node_info.path, code="FRAME_RANGE_VALID"))

    renderer = str(node_info.renderer or "").strip()
    if not renderer or renderer.lower() in ("not set", "unknown"):
        results.append(ValidationResult("ERROR", "Renderer", "No renderer or Hydra delegate is configured.", node_info.path, code="RENDERER_MISSING"))
    else:
        results.append(ValidationResult("PASSED", "Renderer", "Renderer is configured: {}.".format(renderer), node_info.path, code="RENDERER_CONFIGURED"))

    mode = str(node_info.execution_mode or "").lower()
    if mode not in ("hython", "husk"):
        results.append(ValidationResult("ERROR", "Execution", "Unsupported execution mode: {}".format(mode or "Not Set"), node_info.path, code="EXECUTION_MODE_INVALID"))
    else:
        results.append(ValidationResult("PASSED", "Execution", "Execution mode is {}.".format(mode.title()), node_info.path, code="EXECUTION_MODE_VALID"))

    output_path = str(node_info.output_path or "").strip()
    if output_path:
        results.append(ValidationResult("PASSED", "Output", "Final image output is configured.", node_info.path, code="OUTPUT_CONFIGURED"))
        directory = os.path.dirname(output_path)
        if directory and not os.path.isdir(directory):
            results.append(ValidationResult(
                "WARNING", "Output", "The output directory does not exist: {}".format(directory), node_info.path,
                code="OUTPUT_DIRECTORY_MISSING", fixable=True, batch_safe=True,
                data={"path": directory},
            ))
        if node_info.frame_end > node_info.frame_start and not _FRAME_TOKEN.search(output_path):
            results.append(ValidationResult(
                "ERROR", "Output", "Animation output must contain a frame token such as $F4.", node_info.path,
                code="OUTPUT_FRAME_TOKEN_MISSING",
            ))
        extension = os.path.splitext(output_path)[1].lower()
        if extension in (".usd", ".usda", ".usdc"):
            results.append(ValidationResult("ERROR", "Output", "The final image output points to a USD file instead of an image product.", node_info.path, code="OUTPUT_IS_USD"))
    else:
        results.append(ValidationResult(
            "ERROR", "Output", "The selected render source has no final image output.", node_info.path,
            code="OUTPUT_MISSING", fixable=True, requires_confirmation=True,
            data={"node_path": node_info.path},
        ))

    width = int(node_info.resolution_width or 0)
    height = int(node_info.resolution_height or 0)
    if width <= 0 or height <= 0:
        results.append(ValidationResult(
            "ERROR", "Resolution", "Render resolution must be greater than zero.", node_info.path,
            code="RESOLUTION_INVALID", fixable=True, batch_safe=True,
            data={"node_path": node_info.path, "width": 1920, "height": 1080},
        ))
    else:
        results.append(ValidationResult("PASSED", "Resolution", "Resolution is {} × {}.".format(width, height), node_info.path, code="RESOLUTION_VALID"))

    if any(name in renderer.lower() for name in _IMAGE_RENDERERS):
        if node_info.camera:
            results.append(ValidationResult("PASSED", "Camera", "Render camera is configured: {}.".format(node_info.camera), node_info.path, code="CAMERA_CONFIGURED"))
        else:
            results.append(ValidationResult("ERROR", "Camera", "No render camera is configured.", node_info.path, code="CAMERA_MISSING"))

    if mode == "husk" and not str(getattr(node_info, "usd_output_path", "") or "").strip():
        results.append(ValidationResult("WARNING", "Solaris", "No explicit intermediate USD path was found. The USD Render ROP may use a temporary file.", node_info.path, code="USD_OUTPUT_NOT_EXPLICIT"))
    return results
