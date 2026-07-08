import subprocess
from pathlib import Path


MAYA_RENDER_EXE = r"C:\Program Files\Autodesk\Maya2023\bin\Render.exe"

SCENE_PATH = r"D:\Moemen\iti\CGTD\RenderHiveProject\Render\scenes\test_scene.ma"
PROJECT_PATH = r"D:\Moemen\iti\CGTD\RenderHiveProject\Render"
OUTPUT_PATH = r"D:\Moemen\iti\CGTD\RenderHiveProject\Render\movies"


def render_maya_frame(frame):
    render_exe = Path(MAYA_RENDER_EXE)
    scene_path = Path(SCENE_PATH)
    output_path = Path(OUTPUT_PATH)

    if not render_exe.exists():
        raise FileNotFoundError(f"Render.exe not found: {render_exe}")

    if not scene_path.exists():
        raise FileNotFoundError(f"Scene file not found: {scene_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(render_exe),
        "-r", "sw",
        "-s", str(frame),
        "-e", str(frame),
        "-b", "1",
        "-proj", PROJECT_PATH,
        "-rd", OUTPUT_PATH,
        "-cam", "renderCam",
        SCENE_PATH,
    ]

    print("Running command:")
    print(" ".join(f'"{x}"' if " " in x else x for x in cmd))
    print("-" * 60)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    full_log = []

    for line in process.stdout:
        print(line, end="")
        full_log.append(line)

    return_code = process.wait()

    print("-" * 60)
    print("Return code:", return_code)

    if return_code == 0:
        print("Render finished successfully.")
    else:
        print("Render failed.")

    return return_code, "".join(full_log)


if __name__ == "__main__":
    for frame in range(1, 6):
        render_maya_frame(frame=frame)
