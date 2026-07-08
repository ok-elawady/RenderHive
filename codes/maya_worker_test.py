import os
import time
import subprocess
from pathlib import Path

import maya.standalone


# ============================================================
# CONFIG
# ============================================================

MAYA_VERSION = "2023"

MAYA_RENDER_EXE = rf"C:\Program Files\Autodesk\Maya{MAYA_VERSION}\bin\Render.exe"

SCENE_PATH = r"D:\Moemen\iti\CGTD\RenderHiveProject\Render\scenes\test_scene.ma"
PROJECT_PATH = r"D:\Moemen\iti\CGTD\RenderHiveProject\Render"
OUTPUT_PATH = r"D:\Moemen\iti\CGTD\RenderHiveProject\Render\images"

REQUESTED_CAMERA = "renderCam"

# جرب arnold أو sw
RENDERER = "arnold"
# RENDERER = "sw"

FRAME_START = 1
FRAME_END = 5

IMAGE_NAME = "shot01"
IMAGE_FORMAT = "exr"
FRAME_PADDING = 4

LOG_FILE = r"D:\Moemen\iti\CGTD\RenderHiveProject\maya_worker_last_log.txt"


# ============================================================
# UTILS
# ============================================================

def quote_cmd(cmd):
    return " ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd)


def ensure_folder(path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================
# PREFLIGHT
# ============================================================

def preflight_scene():
    print("=" * 70)
    print("STARTING MAYA PREFLIGHT")
    print("=" * 70)

    import maya.cmds as cmds

    errors = []
    warnings = []

    if not os.path.exists(MAYA_RENDER_EXE):
        errors.append(f"Render.exe does not exist: {MAYA_RENDER_EXE}")

    if not os.path.exists(SCENE_PATH):
        errors.append(f"Scene file does not exist: {SCENE_PATH}")

    if not os.path.exists(PROJECT_PATH):
        errors.append(f"Project path does not exist: {PROJECT_PATH}")

    ensure_folder(OUTPUT_PATH)

    if errors:
        return False, errors, warnings

    cmds.file(SCENE_PATH, open=True, force=True)

    camera_shapes = cmds.ls(type="camera") or []
    camera_names = []

    for cam_shape in camera_shapes:
        parents = cmds.listRelatives(cam_shape, parent=True) or []
        if parents:
            camera_names.append(parents[0])

    current_renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer")
    scene_start = cmds.getAttr("defaultRenderGlobals.startFrame")
    scene_end = cmds.getAttr("defaultRenderGlobals.endFrame")

    print("Scene:", SCENE_PATH)
    print("Project:", PROJECT_PATH)
    print("Output:", OUTPUT_PATH)
    print("Scene renderer:", current_renderer)
    print("Requested renderer:", RENDERER)
    print("Scene frame range:", scene_start, "to", scene_end)
    print("Requested frame range:", FRAME_START, "to", FRAME_END)
    print("Available cameras:", camera_names)
    print("Requested camera:", REQUESTED_CAMERA)

    if REQUESTED_CAMERA not in camera_names:
        errors.append(
            f"Camera '{REQUESTED_CAMERA}' does not exist. "
            f"Available cameras: {camera_names}"
        )

    if FRAME_START > FRAME_END:
        errors.append("FRAME_START is greater than FRAME_END.")

    if FRAME_START < scene_start or FRAME_END > scene_end:
        warnings.append(
            "Requested frame range is outside the scene render range. "
            "Render may still work because command line overrides it."
        )

    if current_renderer != RENDERER:
        warnings.append(
            f"Scene renderer is '{current_renderer}', but command will use '{RENDERER}'."
        )

    return len(errors) == 0, errors, warnings


# ============================================================
# OUTPUT NAMING FIX
# ============================================================

def expected_output_name(frame):
    frame_padded = str(frame).zfill(FRAME_PADDING)
    ext = IMAGE_FORMAT.lower().replace(".", "")
    return f"{IMAGE_NAME}.{frame_padded}.{ext}"


def fix_maya_output_names(render_start_time):
    """
    Maya أحيانًا بيطلع الاسم كده:
        shot01.png.0001

    وإحنا عايزينه يبقى:
        shot01.0001.png

    الدالة دي بتدور على الأسماء الغلط وتعيد تسميتها بعد الرندر.
    """

    output_dir = Path(OUTPUT_PATH)
    ext = IMAGE_FORMAT.lower().replace(".", "")
    scene_stem = Path(SCENE_PATH).stem

    print("=" * 70)
    print("FIXING MAYA OUTPUT NAMES")
    print("=" * 70)

    renamed_anything = False

    # لو Maya تجاهل -im لأي سبب، ممكن يستخدم اسم الـscene
    possible_prefixes = [
        IMAGE_NAME,
        scene_stem,
    ]

    for frame in range(FRAME_START, FRAME_END + 1):
        frame_padded = str(frame).zfill(FRAME_PADDING)

        correct_name = f"{IMAGE_NAME}.{frame_padded}.{ext}"
        correct_path = output_dir / correct_name

        # لو الملف أصلاً صح
        if correct_path.exists():
            print(f"Already correct: {correct_path.name}")
            continue

        possible_wrong_names = []

        for prefix in possible_prefixes:
            possible_wrong_names.extend([
                f"{prefix}.{ext}.{frame_padded}",      # shot01.png.0001
                f"{prefix}.{ext}.{frame}",             # shot01.png.1
                f"{prefix}_{frame_padded}.{ext}",      # shot01_0001.png
                f"{prefix}_{frame}.{ext}",             # shot01_1.png
                f"{prefix}.{frame}.{ext}",             # shot01.1.png
                f"{prefix}.{frame_padded}",            # shot01.0001
            ])

        found_wrong_path = None

        # ندور في OUTPUT_PATH كله، حتى لو Maya عمل subfolder
        for wrong_name in possible_wrong_names:
            matches = list(output_dir.rglob(wrong_name))

            for match in matches:
                # نحاول نمسك الملفات الجديدة بس
                try:
                    if match.stat().st_mtime >= render_start_time - 5:
                        found_wrong_path = match
                        break
                except OSError:
                    pass

            if found_wrong_path:
                break

        if found_wrong_path:
            if correct_path.exists():
                correct_path.unlink()

            found_wrong_path.rename(correct_path)
            print(f"Renamed: {found_wrong_path.name} -> {correct_path.name}")
            renamed_anything = True
        else:
            print(
                f"Could not find output for frame {frame}. Expected: {correct_name}")

    if not renamed_anything:
        print("No files needed renaming.")

    print("=" * 70)


# ============================================================
# RENDER
# ============================================================

def run_render():
    print("=" * 70)
    print("STARTING MAYA HEADLESS RENDER")
    print("=" * 70)

    ensure_folder(OUTPUT_PATH)

    cmd = [
        MAYA_RENDER_EXE,

        "-r", RENDERER,

        "-s", str(FRAME_START),
        "-e", str(FRAME_END),
        "-b", "1",

        "-proj", PROJECT_PATH,
        "-rd", OUTPUT_PATH,

        "-im", IMAGE_NAME,
        "-of", IMAGE_FORMAT,
        "-pad", str(FRAME_PADDING),

        # مهم جدًا:
        # بيحاول يجبر Maya يطلع الاسم بالشكل:
        # shot01.0001.png
        "-fnc", "3",

        "-cam", REQUESTED_CAMERA,

        SCENE_PATH,
    ]

    print("Render command:")
    print(quote_cmd(cmd))
    print("=" * 70)

    render_start_time = time.time()

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    render_log = []

    for line in process.stdout:
        print(line, end="")
        render_log.append(line)

    return_code = process.wait()

    full_log = "".join(render_log)

    with open(LOG_FILE, "w", encoding="utf-8", errors="replace") as f:
        f.write(full_log)

    # حتى لو Maya طلع اسم غلط، نصلحه هنا من الكود
    fix_maya_output_names(render_start_time)

    print("=" * 70)
    print("Render return code:", return_code)
    print("Log saved to:", LOG_FILE)

    if return_code == 0:
        print("RENDER SUCCESS")
        return True, full_log

    print("RENDER FAILED")
    return False, full_log


# ============================================================
# MAIN
# ============================================================

def main():
    maya.standalone.initialize(name="python")

    try:
        passed, errors, warnings = preflight_scene()

        if warnings:
            print("=" * 70)
            print("PREFLIGHT WARNINGS")
            print("=" * 70)
            for warning in warnings:
                print("-", warning)

        if not passed:
            print("=" * 70)
            print("PREFLIGHT FAILED")
            print("=" * 70)
            for error in errors:
                print("-", error)

            print("Task status: FAILED")
            return

        print("=" * 70)
        print("PREFLIGHT PASSED")
        print("=" * 70)

    finally:
        maya.standalone.uninitialize()

    render_success, log = run_render()

    if render_success:
        print("Task status: DONE")
    else:
        print("Task status: FAILED")


if __name__ == "__main__":
    main()
