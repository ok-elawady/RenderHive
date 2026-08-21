"""Headless Houdini ROP/LOP runner used by RenderHive Workers."""

from __future__ import print_function

import argparse
import os
import sys


_CAMERA_PARMS = (
    "camera",
    "rendercamera",
    "cameraoverride",
    "lopcamera",
    "vm_camera",
    "ar_camera",
)

_RENDERER_PARMS = (
    "renderer",
    "renderdelegate",
    "delegate",
    "engine",
)

_IMAGE_OUTPUT_PARMS = (
    "vm_picture",
    "ar_picture",
    "RS_outputFileNamePrefix",
    "picture",
    "outputimage",
    "output_image",
    "productname",
    "productName",
    "output_file",
    "outputfile",
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Render one Houdini frame through a ROP/LOP node."
    )
    parser.add_argument("--scene", required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--frame", required=True, type=float)
    parser.add_argument("--camera", default="")
    parser.add_argument("--renderer", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--width", default=0, type=int)
    parser.add_argument("--height", default=0, type=int)
    return parser.parse_args(argv)


def _set_first_parm(node, names, value):
    if value in (None, ""):
        return False
    for name in names:
        try:
            parm = node.parm(name)
        except Exception:
            parm = None
        if parm is None:
            continue
        try:
            parm.set(value)
            return True
        except Exception:
            continue
    return False


def _set_renderer(node, value):
    if not value:
        return False
    target = str(value).strip().lower()
    for name in _RENDERER_PARMS:
        try:
            parm = node.parm(name)
        except Exception:
            parm = None
        if parm is None:
            continue
        try:
            items = list(parm.menuItems())
            labels = list(parm.menuLabels())
        except Exception:
            items = []
            labels = []
        for index, label in enumerate(labels or items):
            normalized = str(label).strip().lower()
            if target == normalized or target in normalized or normalized in target:
                try:
                    parm.set(items[index] if items else label)
                    return True
                except Exception:
                    pass
        try:
            parm.set(value)
            return True
        except Exception:
            continue
    return False


def _set_resolution(node, width, height):
    if int(width or 0) <= 0 or int(height or 0) <= 0:
        return False
    try:
        tuple_parm = node.parmTuple("res")
    except Exception:
        tuple_parm = None
    if tuple_parm is not None:
        try:
            tuple_parm.set((int(width), int(height)))
            return True
        except Exception:
            pass
    width_set = _set_first_parm(node, ("res1", "resolutionx", "width"), int(width))
    height_set = _set_first_parm(node, ("res2", "resolutiony", "height"), int(height))
    return bool(width_set and height_set)


def _stage_for_node(node):
    candidates = [node]
    try:
        candidates.extend([item for item in node.inputs() if item is not None])
    except Exception:
        pass
    for candidate in candidates:
        try:
            method = getattr(candidate, "stage", None)
            if callable(method):
                stage = method()
                if stage is not None:
                    return stage
        except Exception:
            pass
    return None


def _override_usd_product(stage, output_path):
    if stage is None or not output_path:
        return False
    try:
        prims = stage.Traverse()
    except Exception:
        return False
    changed = False
    try:
        for prim in prims:
            try:
                if str(prim.GetTypeName() or "").lower() != "renderproduct":
                    continue
                attribute = prim.GetAttribute("productName")
                if attribute:
                    attribute.Set(str(output_path))
                    changed = True
            except Exception:
                continue
    except Exception:
        pass
    return changed


def apply_overrides(node, args):
    if args.camera and not _set_first_parm(node, _CAMERA_PARMS, args.camera):
        raise RuntimeError(
            "The selected render source does not expose a camera override parameter."
        )

    if args.renderer and not _set_renderer(node, args.renderer):
        raise RuntimeError(
            "The selected render source does not expose a renderer override parameter."
        )

    if args.output:
        applied = _set_first_parm(node, _IMAGE_OUTPUT_PARMS, args.output)
        if not applied:
            applied = _override_usd_product(_stage_for_node(node), args.output)
        if not applied:
            raise RuntimeError(
                "The selected render source does not support a job-level output override."
            )

    if (args.width or args.height) and not _set_resolution(node, args.width, args.height):
        raise RuntimeError(
            "The selected render source does not support a job-level resolution override."
        )


def main(argv=None):
    args = parse_args(argv)
    import hou

    scene_path = os.path.abspath(args.scene)
    if not os.path.isfile(scene_path):
        raise RuntimeError("HIP file does not exist: {}".format(scene_path))

    hou.hipFile.load(
        scene_path,
        suppress_save_prompt=True,
        ignore_load_warnings=True,
    )
    node = hou.node(args.node)
    if node is None:
        raise RuntimeError("Render node does not exist: {}".format(args.node))

    apply_overrides(node, args)

    frame = float(args.frame)
    hou.setFrame(frame)
    render_method = getattr(node, "render", None)
    if not callable(render_method):
        raise RuntimeError("Node is not directly renderable: {}".format(args.node))

    print("RENDERHIVE_FRAME_START {}".format(frame), flush=True)
    render_method(
        frame_range=(frame, frame, 1.0),
        ignore_inputs=False,
        verbose=True,
    )
    print("RENDERHIVE_FRAME_DONE {}".format(frame), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(
            "RenderHive Houdini render failed: {}".format(error),
            file=sys.stderr,
        )
        sys.exit(1)
