
import maya.cmds as cmds


CATEGORY = "Geometry"


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


def get_renderable_mesh_shapes():
    shapes = []

    for shape in cmds.ls(type="mesh", long=True) or []:
        if not cmds.objExists(shape):
            continue

        try:
            if cmds.getAttr(shape + ".intermediateObject"):
                continue
        except Exception:
            pass

        parents = cmds.listRelatives(
            shape,
            parent=True,
            fullPath=True
        ) or []

        if not parents:
            continue

        transform = parents[0]

        try:
            if not cmds.getAttr(transform + ".visibility"):
                continue
        except Exception:
            pass

        shapes.append(shape)

    return shapes


def get_transform(shape):
    parents = cmds.listRelatives(
        shape,
        parent=True,
        fullPath=True
    ) or []

    return parents[0] if parents else shape


def is_referenced(node):
    try:
        return bool(
            cmds.referenceQuery(
                node,
                isNodeReferenced=True
            )
        )
    except Exception:
        return False


def check_empty_meshes(context):
    results = []
    empty = []

    for shape in get_renderable_mesh_shapes():
        try:
            vertex_count = int(
                cmds.polyEvaluate(shape, vertex=True)
            )
            face_count = int(
                cmds.polyEvaluate(shape, face=True)
            )
        except Exception:
            continue

        if vertex_count == 0 or face_count == 0:
            empty.append({
                "shape": shape,
                "transform": get_transform(shape),
                "vertices": vertex_count,
                "faces": face_count,
            })

    for item in empty:
        results.append(make_result(
            "ERROR",
            "EMPTY_MESH",
            (
                "Renderable mesh has no usable geometry: "
                "{transform} ({vertices} vertices, {faces} faces)"
            ).format(**item),
            node=item["transform"],
            data=item
        ))

    if not empty:
        results.append(make_result(
            "PASSED",
            "NO_EMPTY_MESHES",
            "No empty renderable meshes were found."
        ))

    return results


def check_non_manifold_geometry(context):
    results = []
    found = []

    for shape in get_renderable_mesh_shapes():
        try:
            non_manifold_edges = cmds.polyInfo(
                shape,
                nonManifoldEdges=True
            ) or []
        except Exception:
            non_manifold_edges = []

        try:
            non_manifold_vertices = cmds.polyInfo(
                shape,
                nonManifoldVertices=True
            ) or []
        except Exception:
            non_manifold_vertices = []

        if non_manifold_edges or non_manifold_vertices:
            item = {
                "shape": shape,
                "transform": get_transform(shape),
                "edge_count": len(non_manifold_edges),
                "vertex_count": len(non_manifold_vertices),
                "edges": non_manifold_edges,
                "vertices": non_manifold_vertices,
            }
            found.append(item)

    for item in found:
        results.append(make_result(
            "ERROR",
            "NON_MANIFOLD_GEOMETRY",
            (
                "Non-manifold geometry found on {transform}: "
                "{edge_count} edge issue(s), "
                "{vertex_count} vertex issue(s)."
            ).format(**item),
            node=item["transform"],
            data=item
        ))

    if not found:
        results.append(make_result(
            "PASSED",
            "NO_NON_MANIFOLD_GEOMETRY",
            "No non-manifold geometry was found."
        ))

    return results


def check_lamina_faces(context):
    results = []
    found = []

    for shape in get_renderable_mesh_shapes():
        try:
            lamina = cmds.polyInfo(
                shape,
                laminaFaces=True
            ) or []
        except Exception:
            lamina = []

        if lamina:
            found.append({
                "shape": shape,
                "transform": get_transform(shape),
                "count": len(lamina),
                "faces": lamina,
            })

    for item in found:
        results.append(make_result(
            "ERROR",
            "LAMINA_FACES",
            (
                "Lamina faces found on {transform}: "
                "{count} issue(s)."
            ).format(**item),
            node=item["transform"],
            data=item
        ))

    if not found:
        results.append(make_result(
            "PASSED",
            "NO_LAMINA_FACES",
            "No lamina faces were found."
        ))

    return results


def check_transform_scales(context):
    results = []
    zero_scale = []
    negative_scale = []

    transforms = sorted(set(
        get_transform(shape)
        for shape in get_renderable_mesh_shapes()
    ))

    for transform in transforms:
        scales = []

        for axis in "XYZ":
            attr = "{}.scale{}".format(
                transform,
                axis
            )

            try:
                scales.append(
                    float(cmds.getAttr(attr))
                )
            except Exception:
                scales.append(1.0)

        item = {
            "transform": transform,
            "scale": scales,
        }

        if any(
            abs(value) <= 0.000001
            for value in scales
        ):
            zero_scale.append(item)

        elif any(
            value < 0.0
            for value in scales
        ):
            negative_scale.append(item)

    for item in zero_scale:
        results.append(make_result(
            "ERROR",
            "ZERO_GEOMETRY_SCALE",
            "Geometry transform has a zero scale: {}".format(
                item["transform"]
            ),
            node=item["transform"],
            data=item
        ))

    for item in negative_scale:
        results.append(make_result(
            "WARNING",
            "NEGATIVE_GEOMETRY_SCALE",
            (
                "Geometry transform has a negative scale. "
                "This may flip normals or cause inconsistent exports: {}"
            ).format(item["transform"]),
            node=item["transform"],
            data=item
        ))

    if not zero_scale and not negative_scale:
        results.append(make_result(
            "PASSED",
            "GEOMETRY_SCALE_VALID",
            "Renderable geometry has no zero or negative scales."
        ))

    return results


def check_missing_uvs(context):
    results = []
    missing = []

    for shape in get_renderable_mesh_shapes():
        try:
            uv_count = int(
                cmds.polyEvaluate(shape, uv=True)
            )
        except Exception:
            uv_count = 0

        if uv_count == 0:
            missing.append({
                "shape": shape,
                "transform": get_transform(shape),
            })

    for item in missing:
        results.append(make_result(
            "WARNING",
            "MESH_WITHOUT_UVS",
            (
                "Renderable mesh has no UVs. This may be intentional, "
                "but texture-based materials will not map correctly: {}"
            ).format(item["transform"]),
            node=item["transform"],
            data=item
        ))

    if not missing:
        results.append(make_result(
            "PASSED",
            "UVS_AVAILABLE",
            "All renderable meshes contain UV data."
        ))

    return results


def check_render_stats(context):
    results = []
    primary_visibility_off = []
    casts_shadows_off = []

    for shape in get_renderable_mesh_shapes():
        transform = get_transform(shape)

        if cmds.objExists(shape + ".primaryVisibility"):
            try:
                if not cmds.getAttr(
                    shape + ".primaryVisibility"
                ):
                    primary_visibility_off.append({
                        "shape": shape,
                        "transform": transform,
                    })
            except Exception:
                pass

        if cmds.objExists(shape + ".castsShadows"):
            try:
                if not cmds.getAttr(
                    shape + ".castsShadows"
                ):
                    casts_shadows_off.append({
                        "shape": shape,
                        "transform": transform,
                    })
            except Exception:
                pass

    for item in primary_visibility_off:
        results.append(make_result(
            "WARNING",
            "PRIMARY_VISIBILITY_OFF",
            (
                "Renderable mesh has Primary Visibility disabled: {}"
            ).format(item["transform"]),
            node=item["transform"],
            data=item
        ))

    for item in casts_shadows_off:
        results.append(make_result(
            "INFO",
            "CASTS_SHADOWS_OFF",
            (
                "Renderable mesh does not cast shadows: {}"
            ).format(item["transform"]),
            node=item["transform"],
            data=item
        ))

    if (
        not primary_visibility_off
        and not casts_shadows_off
    ):
        results.append(make_result(
            "PASSED",
            "RENDER_STATS_VALID",
            "Geometry render visibility settings look valid."
        ))

    return results


def check_construction_history(context):
    results = []
    high_history = []

    for shape in get_renderable_mesh_shapes():
        transform = get_transform(shape)

        try:
            history = cmds.listHistory(
                shape,
                pruneDagObjects=True
            ) or []
        except Exception:
            history = []

        history = [
            node
            for node in history
            if node not in {shape, transform}
        ]

        # This is intentionally a warning threshold,
        # not a strict production rule.
        if len(history) > 25:
            high_history.append({
                "shape": shape,
                "transform": transform,
                "history_count": len(history),
                "history": history,
            })

    for item in high_history:
        results.append(make_result(
            "WARNING",
            "HEAVY_CONSTRUCTION_HISTORY",
            (
                "Mesh has heavy construction history "
                "({history_count} nodes): {transform}"
            ).format(**item),
            node=item["transform"],
            data=item
        ))

    if not high_history:
        results.append(make_result(
            "PASSED",
            "CONSTRUCTION_HISTORY_REASONABLE",
            "No unusually heavy mesh history was detected."
        ))

    return results


def check_orphan_intermediate_shapes(context):
    results = []
    orphaned = []

    for shape in cmds.ls(type="mesh", long=True) or []:
        try:
            is_intermediate = bool(
                cmds.getAttr(
                    shape + ".intermediateObject"
                )
            )
        except Exception:
            is_intermediate = False

        if not is_intermediate:
            continue

        outputs = cmds.listConnections(
            shape,
            source=False,
            destination=True
        ) or []

        if outputs:
            continue

        transform = get_transform(shape)

        if is_referenced(shape):
            continue

        orphaned.append({
            "shape": shape,
            "transform": transform,
        })

    for item in orphaned:
        results.append(make_result(
            "WARNING",
            "ORPHAN_INTERMEDIATE_SHAPE",
            (
                "Unused intermediate mesh shape found: {}"
            ).format(item["shape"]),
            node=item["transform"],
            data=item
        ))

    if not orphaned:
        results.append(make_result(
            "PASSED",
            "NO_ORPHAN_INTERMEDIATE_SHAPES",
            "No unused intermediate mesh shapes were found."
        ))

    return results


def run_checks(context):
    results = []

    checks = [
        check_empty_meshes,
        check_non_manifold_geometry,
        check_lamina_faces,
        check_transform_scales,
        check_missing_uvs,
        check_render_stats,
        check_construction_history,
        check_orphan_intermediate_shapes,
    ]

    for check in checks:
        try:
            check_results = check(context)

            if check_results:
                results.extend(check_results)

        except Exception as error:
            results.append(make_result(
                "ERROR",
                "GEOMETRY_CHECK_FAILED",
                "Check '{}' failed: {}".format(
                    check.__name__,
                    error
                )
            ))

    return results
