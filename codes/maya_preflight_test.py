import maya.cmds as cmds
import os
import maya.standalone

maya.standalone.initialize(name="python")


SCENE_PATH = r"D:\Moemen\iti\CGTD\RenderHiveProject\Render\scenes\test_scene.ma"


def preflight_scene(scene_path):
    if not os.path.exists(scene_path):
        raise FileNotFoundError(scene_path)

    cmds.file(scene_path, open=True, force=True)

    cameras = cmds.ls(type="camera") or []
    renderable_cameras = []

    for cam_shape in cameras:
        is_renderable = cmds.getAttr(cam_shape + ".renderable")
        if is_renderable:
            parent = cmds.listRelatives(cam_shape, parent=True)
            if parent:
                renderable_cameras.append(parent[0])

    start_frame = cmds.getAttr("defaultRenderGlobals.startFrame")
    end_frame = cmds.getAttr("defaultRenderGlobals.endFrame")
    current_renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer")

    print("Scene:", scene_path)
    print("Renderer:", current_renderer)
    print("Frame range:", start_frame, "to", end_frame)
    print("Renderable cameras:", renderable_cameras)

    if not renderable_cameras:
        print("ERROR: No renderable camera found.")
    else:
        print("Preflight passed.")


try:
    preflight_scene(SCENE_PATH)
finally:
    maya.standalone.uninitialize()
