"""Render-node, camera and output validation checks."""

from __future__ import absolute_import

from renderhive_houdini.validation.result import ValidationResult


def run(node_info):
    if node_info is None:
        return [ValidationResult(
            "ERROR",
            "Render",
            "Select an executable ROP or Solaris render node.",
        )]

    results = [ValidationResult(
        "PASSED",
        "Render",
        "Render node detected: {}".format(node_info.path),
        node_info.path,
    )]

    if node_info.is_bypassed:
        results.append(ValidationResult(
            "ERROR",
            "Render",
            "The selected render node is bypassed.",
            node_info.path,
        ))

    if node_info.frame_end < node_info.frame_start:
        results.append(ValidationResult(
            "ERROR",
            "Frames",
            "Render end frame is before the start frame.",
            node_info.path,
        ))
    elif node_info.frame_step <= 0:
        results.append(ValidationResult(
            "ERROR",
            "Frames",
            "Render frame step must be greater than zero.",
            node_info.path,
        ))
    else:
        results.append(ValidationResult(
            "PASSED",
            "Frames",
            "Frame range is valid: {}–{} step {}.".format(
                node_info.frame_start,
                node_info.frame_end,
                node_info.frame_step,
            ),
            node_info.path,
        ))

    if node_info.output_path:
        results.append(ValidationResult(
            "PASSED",
            "Output",
            "Output path is configured.",
            node_info.path,
        ))
    else:
        results.append(ValidationResult(
            "ERROR",
            "Output",
            "The selected render node has no output path.",
            node_info.path,
        ))

    image_renderers = (
        "karma",
        "arnold",
        "redshift",
        "mantra",
        "renderman",
        "v-ray",
        "usd render",
    )
    if any(name in node_info.renderer.lower() for name in image_renderers):
        if node_info.camera:
            results.append(ValidationResult(
                "PASSED",
                "Camera",
                "Render camera is configured.",
                node_info.path,
            ))
        else:
            results.append(ValidationResult(
                "WARNING",
                "Camera",
                "No explicit camera was found on the selected render node.",
                node_info.path,
            ))

    return results
