"""Render a Houdini ROP/LOP node from hython.

This script intentionally uses only the Houdini Object Model bundled with the
selected Houdini installation. It supports traditional /out ROPs and renderable
LOP nodes that expose the standard ROP render API.
"""

from __future__ import print_function

import argparse
import os
import sys
import traceback


def _existing_parm(node, names):
    for name in names:
        try:
            parm = node.parm(name)
        except Exception:
            parm = None
        if parm is not None:
            return parm
    return None


def _set_string(node, names, value):
    if not value:
        return False
    parm = _existing_parm(node, names)
    if parm is None:
        return False
    try:
        parm.set(str(value))
        return True
    except Exception:
        return False


def _set_integer(node, names, value):
    if value is None:
        return False
    parm = _existing_parm(node, names)
    if parm is None:
        return False
    try:
        parm.set(int(value))
        return True
    except Exception:
        return False


def _apply_overrides(node, args):
    changed = []

    if _set_string(
        node,
        (
            "camera",
            "cam",
            "camera_path",
            "render_camera",
            "lopcamera",
        ),
        args.camera,
    ):
        changed.append("camera")

    if _set_string(
        node,
        (
            "vm_picture",
            "picture",
            "ar_picture",
            "RS_outputFileNamePrefix",
            "outputimage",
            "output",
            "lopoutput",
        ),
        args.output,
    ):
        changed.append("output")

    if _set_string(
        node,
        (
            "renderer",
            "renderdelegate",
            "renderername",
            "delegate",
        ),
        args.renderer,
    ):
        changed.append("renderer")

    if _set_integer(node, ("res1", "width", "xres"), args.width):
        changed.append("width")
    if _set_integer(node, ("res2", "height", "yres"), args.height):
        changed.append("height")

    if changed:
        print("RENDERHIVE_OVERRIDES {}".format(",".join(changed)))


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Render a Houdini ROP node.")
    parser.add_argument("--scene", required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--start", type=float)
    parser.add_argument("--end", type=float)
    parser.add_argument("--step", type=float, default=1.0)
    parser.add_argument("--frame", type=float)
    parser.add_argument("--camera", default="")
    parser.add_argument("--renderer", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    try:
        import hou
    except Exception as error:
        print("RENDERHIVE_ERROR Unable to import hou: {}".format(error))
        return 10

    scene_path = os.path.abspath(os.path.expandvars(args.scene))
    if not os.path.isfile(scene_path):
        print("RENDERHIVE_ERROR HIP file does not exist: {}".format(scene_path))
        return 11

    try:
        print("RENDERHIVE_LOAD {}".format(scene_path))
        hou.hipFile.load(scene_path, suppress_save_prompt=True, ignore_load_warnings=True)
    except Exception:
        print("RENDERHIVE_ERROR Failed to load HIP file")
        traceback.print_exc()
        return 12

    node = hou.node(args.node)
    if node is None:
        print("RENDERHIVE_ERROR Render node does not exist: {}".format(args.node))
        return 13

    try:
        if hasattr(node, "isBypassed") and node.isBypassed():
            print("RENDERHIVE_ERROR Render node is bypassed: {}".format(args.node))
            return 14
    except Exception:
        pass

    _apply_overrides(node, args)

    if args.frame is not None:
        start = end = float(args.frame)
    else:
        start = float(args.start if args.start is not None else 1.0)
        end = float(args.end if args.end is not None else start)
    step = max(float(args.step or 1.0), 0.000001)

    try:
        print("RENDERHIVE_RENDER node={} range={}:{}:{}".format(args.node, start, end, step))
        if not hasattr(node, "render"):
            print("RENDERHIVE_ERROR Selected node is not renderable: {}".format(args.node))
            return 15

        node.render(
            frame_range=(start, end, step),
            verbose=True,
            output_progress=True,
        )
        print("RENDERHIVE_SUCCESS node={} range={}:{}:{}".format(args.node, start, end, step))
        return 0
    except Exception:
        print("RENDERHIVE_ERROR Houdini render failed")
        traceback.print_exc()
        return 20


if __name__ == "__main__":
    sys.exit(main())
