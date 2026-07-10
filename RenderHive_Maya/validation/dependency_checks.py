from __future__ import print_function

from core import dependency_collector


CATEGORY = "Dependencies"


def make_result(
    severity,
    code,
    message,
    node="",
    fixable=False,
    data=None
):
    return {
        "severity": severity,
        "category": CATEGORY,
        "code": code,
        "node": node or "",
        "message": message,
        "fixable": bool(fixable),
        "data": data or {},
    }


def get_display_name(dependency):
    node = dependency.get("node") or ""
    category = dependency.get(
        "category",
        "dependency"
    )

    if node:
        return "{} ({})".format(
            node,
            category
        )

    return category


def check_dependency_manifest(context):
    results = []

    manifest = dependency_collector.build_manifest(
        context
    )

    dependencies = manifest["dependencies"]

    if not dependencies:
        results.append(make_result(
            "INFO",
            "NO_EXTERNAL_DEPENDENCIES",
            (
                "No supported external scene dependencies "
                "were detected."
            ),
            data={"manifest": manifest}
        ))
        return results

    missing = []
    unresolved_environment = []
    external_local = []
    external_network = []
    absolute_inside_project = []
    portable = []

    for dependency in dependencies:
        status = dependency.get(
            "status",
            ""
        )

        if status == "missing":
            missing.append(dependency)

        elif status == "unresolved_environment":
            unresolved_environment.append(
                dependency
            )

        elif status == "external_local":
            external_local.append(
                dependency
            )

        elif status == "external_network":
            external_network.append(
                dependency
            )

        elif status == "absolute_inside_project":
            absolute_inside_project.append(
                dependency
            )

        elif status == "portable":
            portable.append(dependency)

    for dependency in missing:
        results.append(make_result(
            "ERROR",
            "DEPENDENCY_MISSING",
            "Missing {} path: {}".format(
                get_display_name(dependency),
                dependency.get(
                    "original_path",
                    ""
                )
            ),
            node=dependency.get("node", ""),
            data=dependency
        ))

    for dependency in unresolved_environment:
        results.append(make_result(
            "ERROR",
            "UNRESOLVED_ENVIRONMENT_PATH",
            (
                "Dependency path contains an unresolved "
                "environment variable: {}"
            ).format(
                dependency.get(
                    "original_path",
                    ""
                )
            ),
            node=dependency.get("node", ""),
            data=dependency
        ))

    for dependency in external_local:
        results.append(make_result(
            "ERROR",
            "LOCAL_DEPENDENCY_OUTSIDE_PROJECT",
            (
                "Dependency is stored outside the Maya "
                "project on a local path and is not portable "
                "to another machine: {}"
            ).format(
                dependency.get(
                    "resolved_path",
                    ""
                )
            ),
            node=dependency.get("node", ""),
            data=dependency
        ))

    for dependency in external_network:
        results.append(make_result(
            "WARNING",
            "NETWORK_DEPENDENCY_OUTSIDE_PROJECT",
            (
                "Dependency uses an external network path. "
                "Every worker must have access to the same "
                "share: {}"
            ).format(
                dependency.get(
                    "resolved_path",
                    ""
                )
            ),
            node=dependency.get("node", ""),
            data=dependency
        ))

    for dependency in absolute_inside_project:
        results.append(make_result(
            "WARNING",
            "ABSOLUTE_DEPENDENCY_PATH",
            (
                "Dependency exists inside the Maya project "
                "but is saved as an absolute path. "
                "Relative project paths are safer for worker "
                "path remapping: {}"
            ).format(
                dependency.get(
                    "resolved_path",
                    ""
                )
            ),
            node=dependency.get("node", ""),
            fixable=False,
            data=dependency
        ))

    blocking_count = (
        len(missing)
        + len(unresolved_environment)
        + len(external_local)
    )

    if blocking_count == 0:
        results.append(make_result(
            "PASSED",
            "DEPENDENCIES_AVAILABLE",
            (
                "All {} detected dependencies are available "
                "to the current project or shared network."
            ).format(len(dependencies)),
            data={
                "total": len(dependencies),
                "manifest": manifest,
            }
        ))

    if (
        dependencies
        and len(portable) == len(dependencies)
    ):
        results.append(make_result(
            "PASSED",
            "ALL_DEPENDENCIES_PORTABLE",
            (
                "All detected dependencies use portable "
                "project-relative paths."
            ),
            data={"manifest": manifest}
        ))

    elif portable:
        results.append(make_result(
            "INFO",
            "PORTABLE_DEPENDENCY_COUNT",
            "{} of {} dependencies are fully portable.".format(
                len(portable),
                len(dependencies)
            ),
            data={
                "portable_count": len(portable),
                "total": len(dependencies),
            }
        ))

    results.append(make_result(
        "INFO",
        "DEPENDENCY_MANIFEST_READY",
        (
            "Dependency manifest collected {} item(s). "
            "The same data can be sent to the backend later."
        ).format(len(dependencies)),
        data={"manifest": manifest}
    ))

    return results


def run_checks(context):
    try:
        return check_dependency_manifest(
            context
        )

    except Exception as error:
        return [
            make_result(
                "ERROR",
                "DEPENDENCY_CHECK_FAILED",
                "Dependency validation failed: {}".format(
                    error
                )
            )
        ]
