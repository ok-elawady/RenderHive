"""HIP-file and project validation checks."""

from __future__ import absolute_import

from renderhive_houdini.validation.result import ValidationResult


def run(context):
    results = []

    if context.is_new_file or not context.hip_path:
        results.append(ValidationResult(
            "ERROR",
            "Scene",
            "Save the HIP file before submitting it to the farm.",
        ))
    else:
        results.append(ValidationResult(
            "PASSED",
            "Scene",
            "HIP file is saved.",
        ))

    if context.has_unsaved_changes:
        results.append(ValidationResult(
            "WARNING",
            "Scene",
            "The HIP file contains unsaved changes.",
        ))
    else:
        results.append(ValidationResult(
            "PASSED",
            "Scene",
            "No unsaved scene changes detected.",
        ))

    if context.job_directory:
        results.append(ValidationResult(
            "PASSED",
            "Project",
            "$JOB is configured: {}".format(context.job_directory),
        ))
    else:
        results.append(ValidationResult(
            "WARNING",
            "Project",
            "$JOB is not configured. Shared project paths are recommended.",
        ))

    if context.frame_end < context.frame_start:
        results.append(ValidationResult(
            "ERROR",
            "Timeline",
            "The Houdini timeline end frame is before the start frame.",
        ))

    return results
