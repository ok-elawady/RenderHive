"""HIP-file, project and timeline validation checks."""

from __future__ import absolute_import

import os

from renderhive_houdini.validation.result import ValidationResult


def _inside(child, parent):
    if not child or not parent:
        return False
    try:
        child = os.path.normcase(os.path.abspath(child))
        parent = os.path.normcase(os.path.abspath(parent))
        return os.path.commonpath((child, parent)) == parent
    except Exception:
        return False


def run(context):
    results = []
    if context is None:
        return [ValidationResult("ERROR", "Scene", "Houdini scene context is unavailable.", code="SCENE_CONTEXT_MISSING")]

    if context.is_new_file or not context.hip_path:
        results.append(ValidationResult(
            "ERROR", "Scene", "Save the HIP file before submitting it to the farm.",
            code="SCENE_UNSAVED", fixable=True, requires_confirmation=True,
        ))
    elif not os.path.isfile(context.hip_path):
        results.append(ValidationResult(
            "ERROR", "Scene", "The HIP file does not exist on disk: {}".format(context.hip_path),
            code="SCENE_FILE_MISSING",
        ))
    else:
        results.append(ValidationResult("PASSED", "Scene", "HIP file is saved.", code="SCENE_SAVED"))

    if context.has_unsaved_changes:
        results.append(ValidationResult(
            "WARNING", "Scene", "The HIP file contains unsaved changes.",
            code="SCENE_DIRTY", fixable=True, batch_safe=False, requires_confirmation=True,
        ))
    else:
        results.append(ValidationResult("PASSED", "Scene", "No unsaved scene changes detected.", code="SCENE_CLEAN"))

    if context.project_path and os.path.isdir(context.project_path):
        results.append(ValidationResult("PASSED", "Project", "Project path is available: {}".format(context.project_path), code="PROJECT_AVAILABLE"))
    else:
        results.append(ValidationResult(
            "ERROR", "Project", "A valid shared project path is required.",
            code="PROJECT_INVALID", fixable=bool(context.hip_directory), batch_safe=True,
            data={"suggested_path": context.hip_directory or ""},
        ))

    if context.job_directory:
        results.append(ValidationResult("PASSED", "Project", "$JOB is configured: {}".format(context.job_directory), code="JOB_CONFIGURED"))
    else:
        results.append(ValidationResult(
            "WARNING", "Project", "$JOB is not configured. Shared project paths are recommended.",
            code="JOB_NOT_SET", fixable=bool(context.hip_directory), batch_safe=True,
            data={"path": context.hip_directory or ""},
        ))

    if context.hip_path and context.project_path and not _inside(context.hip_path, context.project_path):
        results.append(ValidationResult(
            "WARNING", "Project", "The HIP file is outside the project path and may not be available to farm workers.",
            code="SCENE_OUTSIDE_PROJECT",
        ))

    if context.frame_end < context.frame_start:
        results.append(ValidationResult("ERROR", "Timeline", "The timeline end frame is before the start frame.", code="TIMELINE_INVALID"))
    else:
        results.append(ValidationResult("PASSED", "Timeline", "Timeline range is valid: {}–{}.".format(context.frame_start, context.frame_end), code="TIMELINE_VALID"))

    if float(context.fps or 0) <= 0:
        results.append(ValidationResult("ERROR", "Timeline", "Scene FPS must be greater than zero.", code="FPS_INVALID"))
    else:
        results.append(ValidationResult("PASSED", "Timeline", "Scene FPS is {}.".format(context.fps), code="FPS_VALID"))
    return results
