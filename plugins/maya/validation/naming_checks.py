import json
import os
import re

import maya.cmds as cmds


CATEGORY = "Naming"


DEFAULT_RULES = {
    "enabled": True,
    "allowed_name_pattern": r"^[A-Za-z_][A-Za-z0-9_]*$",
    "warn_on_non_ascii": True,
    "check_default_names": True,
    "check_duplicate_short_names": True,
    "check_shape_names": True,
    "check_namespaces": True,
    "default_name_patterns": [
        r"^p(Cube|Sphere|Cylinder|Cone|Plane|Torus|Pipe|Prism|Pyramid|Helix)\d+$",
        r"^polySurface\d+$",
        r"^nurbs(Circle|Sphere|Cube|Plane|Cylinder|Cone|Torus)\d+$",
        r"^curve\d+$",
        r"^locator\d+$",
        r"^camera\d+$",
        r"^(point|spot|directional|area|volume)Light\d+$",
        r"^ai(AreaLight|SkyDomeLight|PhotometricLight|MeshLight)\d+$",
        r"^(lambert|blinn|phong|phongE|surfaceShader|useBackground)\d+$",
        r"^(standardSurface|aiStandardSurface|material)\d+$",
        r"^(shadingGroup|set)\d+$",
        r"^group\d+$"
    ],
    "ignored_exact_names": [
        "persp",
        "top",
        "front",
        "side",
        "perspShape",
        "topShape",
        "frontShape",
        "sideShape",
        "defaultLightSet",
        "defaultObjectSet",
        "initialShadingGroup",
        "initialParticleSE",
        "lambert1",
        "particleCloud1"
    ],
    "ignored_prefixes": [
        "default",
        "initial"
    ]
}


CHECKED_NODE_TYPES = [
    "transform",
    "mesh",
    "nurbsCurve",
    "nurbsSurface",
    "camera",
    "locator",
    "light",
    "shadingEngine",
    "lambert",
    "blinn",
    "phong",
    "phongE",
    "surfaceShader",
    "useBackground",
    "standardSurface",
    "aiStandardSurface",
]


MATERIAL_NODE_TYPES = [
    "lambert",
    "blinn",
    "phong",
    "phongE",
    "surfaceShader",
    "useBackground",
    "standardSurface",
    "aiStandardSurface",
]


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


def get_package_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_rules_path():
    return os.path.join(
        get_package_root(),
        "config",
        "validation_rules.json"
    )


def merge_dict(base, override):
    result = dict(base)

    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dict(result[key], value)
        else:
            result[key] = value

    return result


def load_rules():
    rules = dict(DEFAULT_RULES)
    path = get_rules_path()

    if not os.path.exists(path):
        return rules

    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)

        naming_rules = data.get("naming", {})
        rules = merge_dict(rules, naming_rules)

    except Exception:
        # A broken local config must not break all validation.
        pass

    return rules


def get_leaf_name(node):
    return node.rsplit("|", 1)[-1]


def split_namespace(name):
    if ":" not in name:
        return "", name

    parts = name.split(":")
    return ":".join(parts[:-1]), parts[-1]


def is_referenced(node):
    try:
        return bool(cmds.referenceQuery(node, isNodeReferenced=True))
    except Exception:
        return False


def should_ignore(name, rules):
    leaf = get_leaf_name(name)
    _, base_name = split_namespace(leaf)

    if base_name in rules.get("ignored_exact_names", []):
        return True

    for prefix in rules.get("ignored_prefixes", []):
        if base_name.startswith(prefix):
            return True

    return False


def collect_nodes(rules):
    nodes = []
    seen = set()

    for node_type in CHECKED_NODE_TYPES:
        try:
            type_nodes = cmds.ls(type=node_type, long=True) or []
        except Exception:
            type_nodes = []

        for node in type_nodes:
            if node in seen:
                continue

            if should_ignore(node, rules):
                continue

            seen.add(node)
            nodes.append(node)

    return nodes


def check_illegal_names(context, rules):
    results = []
    allowed_pattern = re.compile(
        rules.get(
            "allowed_name_pattern",
            DEFAULT_RULES["allowed_name_pattern"]
        )
    )

    invalid_nodes = []
    non_ascii_nodes = []

    for node in collect_nodes(rules):
        leaf = get_leaf_name(node)
        _, base_name = split_namespace(leaf)

        if not base_name:
            continue

        try:
            base_name.encode("ascii")
            is_ascii = True
        except UnicodeEncodeError:
            is_ascii = False

        if not is_ascii:
            if rules.get("warn_on_non_ascii", True):
                non_ascii_nodes.append(node)
            continue

        if not allowed_pattern.match(base_name):
            invalid_nodes.append(node)

    for node in invalid_nodes:
        results.append(make_result(
            "ERROR",
            "INVALID_NODE_NAME",
            (
                "Node name contains spaces, symbols, or starts with a number. "
                "Use letters, numbers, and underscores only: {}"
            ).format(get_leaf_name(node)),
            node=node,
            fixable=False,
            data={"name": get_leaf_name(node)}
        ))

    for node in non_ascii_nodes:
        results.append(make_result(
            "WARNING",
            "NON_ASCII_NODE_NAME",
            (
                "Node name contains non-ASCII characters and may cause "
                "portability problems on another machine: {}"
            ).format(get_leaf_name(node)),
            node=node,
            fixable=False,
            data={"name": get_leaf_name(node)}
        ))

    if not invalid_nodes and not non_ascii_nodes:
        results.append(make_result(
            "PASSED",
            "NODE_NAMES_LEGAL",
            "Checked node names use portable characters."
        ))

    return results


def check_default_names(context, rules):
    if not rules.get("check_default_names", True):
        return []

    results = []
    patterns = [
        re.compile(pattern, re.IGNORECASE)
        for pattern in rules.get("default_name_patterns", [])
    ]

    default_named_nodes = []

    for node in collect_nodes(rules):
        if is_referenced(node):
            continue

        leaf = get_leaf_name(node)
        _, base_name = split_namespace(leaf)

        if any(pattern.match(base_name) for pattern in patterns):
            default_named_nodes.append(node)

    for node in default_named_nodes:
        results.append(make_result(
            "WARNING",
            "DEFAULT_NODE_NAME",
            (
                "Node still uses an autogenerated Maya name: {}. "
                "Rename it to a meaningful production name."
            ).format(get_leaf_name(node)),
            node=node,
            fixable=False,
            data={"name": get_leaf_name(node)}
        ))

    if not default_named_nodes:
        results.append(make_result(
            "PASSED",
            "NO_DEFAULT_NODE_NAMES",
            "No obvious autogenerated Maya names were found."
        ))

    return results


def check_duplicate_short_names(context, rules):
    if not rules.get("check_duplicate_short_names", True):
        return []

    results = []
    groups = {}

    for node in collect_nodes(rules):
        leaf = get_leaf_name(node)
        groups.setdefault(leaf, []).append(node)

    duplicate_groups = {
        name: paths
        for name, paths in groups.items()
        if len(paths) > 1
    }

    for short_name, paths in sorted(duplicate_groups.items()):
        results.append(make_result(
            "WARNING",
            "DUPLICATE_SHORT_NAME",
            (
                "Multiple DAG nodes use the same short name '{}'. "
                "Full paths will be required and scripts may become ambiguous."
            ).format(short_name),
            node=paths[0],
            fixable=False,
            data={
                "short_name": short_name,
                "nodes": paths,
                "count": len(paths)
            }
        ))

    if not duplicate_groups:
        results.append(make_result(
            "PASSED",
            "NO_DUPLICATE_SHORT_NAMES",
            "No duplicate short node names were found."
        ))

    return results


def check_shape_names(context, rules):
    if not rules.get("check_shape_names", True):
        return []

    results = []
    mismatches = []

    transforms = cmds.ls(type="transform", long=True) or []

    for transform in transforms:
        if should_ignore(transform, rules):
            continue

        if is_referenced(transform):
            continue

        shapes = cmds.listRelatives(
            transform,
            shapes=True,
            noIntermediate=True,
            fullPath=True
        ) or []

        if len(shapes) != 1:
            continue

        shape = shapes[0]
        shape_type = cmds.nodeType(shape)

        if shape_type not in [
            "mesh",
            "nurbsCurve",
            "nurbsSurface",
            "camera",
            "locator"
        ] and not cmds.objectType(shape, isAType="light"):
            continue

        transform_leaf = get_leaf_name(transform)
        shape_leaf = get_leaf_name(shape)

        transform_namespace, transform_base = split_namespace(transform_leaf)
        shape_namespace, shape_base = split_namespace(shape_leaf)

        expected_base = transform_base + "Shape"

        if shape_base != expected_base:
            mismatches.append({
                "transform": transform,
                "shape": shape,
                "current_shape_name": shape_leaf,
                "expected_shape_name": (
                    transform_namespace + ":" + expected_base
                    if transform_namespace else expected_base
                )
            })

    for item in mismatches:
        results.append(make_result(
            "WARNING",
            "SHAPE_NAME_MISMATCH",
            (
                "Shape '{}' does not match its transform '{}'. "
                "Expected shape name: '{}'."
            ).format(
                item["current_shape_name"],
                get_leaf_name(item["transform"]),
                item["expected_shape_name"]
            ),
            node=item["shape"],
            fixable=True,
            data=item
        ))

    if not mismatches:
        results.append(make_result(
            "PASSED",
            "SHAPE_NAMES_MATCH",
            "Shape names match their transform names."
        ))

    return results


def check_namespaces(context, rules):
    if not rules.get("check_namespaces", True):
        return []

    namespaces = set()
    non_referenced_namespace_nodes = []

    for node in collect_nodes(rules):
        leaf = get_leaf_name(node)
        namespace, _ = split_namespace(leaf)

        if not namespace:
            continue

        namespaces.add(namespace)

        if not is_referenced(node):
            non_referenced_namespace_nodes.append(node)

    results = []

    if namespaces:
        results.append(make_result(
            "INFO",
            "NAMESPACES_FOUND",
            "Scene uses namespace(s): {}.".format(
                ", ".join(sorted(namespaces))
            ),
            data={"namespaces": sorted(namespaces)}
        ))

    if non_referenced_namespace_nodes:
        results.append(make_result(
            "WARNING",
            "LOCAL_NODES_IN_NAMESPACE",
            (
                "Found {} non-referenced node(s) inside namespaces. "
                "Confirm these namespaces are intentional."
            ).format(len(non_referenced_namespace_nodes)),
            node=non_referenced_namespace_nodes[0],
            data={"nodes": non_referenced_namespace_nodes}
        ))
    elif not namespaces:
        results.append(make_result(
            "PASSED",
            "NO_NAMESPACES",
            "No custom namespaces were found."
        ))

    return results


def check_task_names(context, rules):
    results = []
    allowed_pattern = re.compile(
        rules.get(
            "allowed_name_pattern",
            DEFAULT_RULES["allowed_name_pattern"]
        )
    )

    fields = [
        ("job_name", "Job name"),
        ("project_name", "Project name"),
        ("image_name", "Image name"),
    ]

    failed = False

    for key, label in fields:
        value = str(context.get(key, "") or "").strip()

        if not value:
            results.append(make_result(
                "ERROR",
                "EMPTY_TASK_NAME",
                "{} is empty.".format(label),
                data={"field": key}
            ))
            failed = True
            continue

        try:
            value.encode("ascii")
            is_ascii = True
        except UnicodeEncodeError:
            is_ascii = False

        if not is_ascii:
            results.append(make_result(
                "WARNING",
                "NON_ASCII_TASK_NAME",
                (
                    "{} contains non-ASCII characters and may be unsafe "
                    "for another worker: {}"
                ).format(label, value),
                data={"field": key, "value": value}
            ))
            continue

        if not allowed_pattern.match(value):
            results.append(make_result(
                "ERROR",
                "INVALID_TASK_NAME",
                (
                    "{} must start with a letter or underscore and use "
                    "letters, numbers, and underscores only: {}"
                ).format(label, value),
                data={"field": key, "value": value}
            ))
            failed = True

    if not failed:
        results.append(make_result(
            "PASSED",
            "TASK_NAMES_VALID",
            "Job, project, and image names are valid."
        ))

    return results


def run_checks(context):
    rules = load_rules()

    if not rules.get("enabled", True):
        return [make_result(
            "INFO",
            "NAMING_CHECKS_DISABLED",
            "Naming validation is disabled in validation_rules.json."
        )]

    results = []

    checks = [
        check_task_names,
        check_illegal_names,
        check_default_names,
        check_duplicate_short_names,
        check_shape_names,
        check_namespaces,
    ]

    for check in checks:
        try:
            check_results = check(context, rules)

            if check_results:
                results.extend(check_results)

        except Exception as error:
            results.append(make_result(
                "ERROR",
                "NAMING_CHECK_FAILED",
                "Check '{}' failed: {}".format(
                    check.__name__,
                    error
                )
            ))

    return results
