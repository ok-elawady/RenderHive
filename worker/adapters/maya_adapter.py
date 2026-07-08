import os
import time
import subprocess
from pathlib import Path


class MayaAdapter:
    def __init__(self, maya_render_exe, log_folder):
        self.maya_render_exe = maya_render_exe
        self.log_folder = log_folder

    # ============================================================
    # UTILS
    # ============================================================

    def ensure_folder(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)

    def quote_cmd(self, cmd):
        return " ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd)

    def get_task_log_path(self, task):
        self.ensure_folder(self.log_folder)
        return str(
            Path(self.log_folder)
            / f"job_{task['job_id']}_task_{task['task_id']}.log"
        )

    # ============================================================
    # PREFLIGHT
    # ============================================================

    def preflight(self, task):
        """
        Preflight = فحص قبل الرندر.
        بنتأكد إن الملف موجود، الكاميرا موجودة، الفريمات صح، والـRender.exe موجود.
        """

        print("=" * 70)
        print("STARTING MAYA PREFLIGHT")
        print("=" * 70)

        import maya.cmds as cmds

        errors = []
        warnings = []

        scene_path = task["scene_path"]
        project_path = task["project_path"]
        output_path = task["output_path"]
        requested_camera = task["camera"]
        requested_renderer = task.get("renderer", "arnold")

        frame_start = int(task["frame_start"])
        frame_end = int(task["frame_end"])

        if not os.path.exists(self.maya_render_exe):
            errors.append(f"Render.exe does not exist: {self.maya_render_exe}")

        if not os.path.exists(scene_path):
            errors.append(f"Scene file does not exist: {scene_path}")

        if not os.path.exists(project_path):
            errors.append(f"Project path does not exist: {project_path}")

        self.ensure_folder(output_path)

        if errors:
            return {
                "passed": False,
                "errors": errors,
                "warnings": warnings,
            }

        cmds.file(scene_path, open=True, force=True)

        camera_shapes = cmds.ls(type="camera") or []
        camera_names = []

        for cam_shape in camera_shapes:
            parents = cmds.listRelatives(cam_shape, parent=True) or []
            if parents:
                camera_names.append(parents[0])

        current_renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer")
        scene_start = cmds.getAttr("defaultRenderGlobals.startFrame")
        scene_end = cmds.getAttr("defaultRenderGlobals.endFrame")

        print("Scene:", scene_path)
        print("Project:", project_path)
        print("Output:", output_path)
        print("Scene renderer:", current_renderer)
        print("Requested renderer:", requested_renderer)
        print("Scene frame range:", scene_start, "to", scene_end)
        print("Requested frame range:", frame_start, "to", frame_end)
        print("Available cameras:", camera_names)
        print("Requested camera:", requested_camera)

        if requested_camera not in camera_names:
            errors.append(
                f"Camera '{requested_camera}' does not exist. "
                f"Available cameras: {camera_names}"
            )

        if frame_start > frame_end:
            errors.append("frame_start is greater than frame_end.")

        if frame_start < scene_start or frame_end > scene_end:
            warnings.append(
                "Requested frame range is outside the scene render range. "
                "Command line render may still work because it overrides scene settings."
            )

        if current_renderer != requested_renderer:
            warnings.append(
                f"Scene renderer is '{current_renderer}', "
                f"but command will use '{requested_renderer}'."
            )

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "scene_renderer": current_renderer,
            "scene_frame_start": scene_start,
            "scene_frame_end": scene_end,
            "available_cameras": camera_names,
        }

    # ============================================================
    # RENDER COMMAND
    # ============================================================

    def build_render_command(self, task):
        scene_path = task["scene_path"]
        project_path = task["project_path"]
        output_path = task["output_path"]

        frame_start = int(task["frame_start"])
        frame_end = int(task["frame_end"])

        renderer = task.get("renderer", "arnold")
        camera = task["camera"]

        image_name = task.get("image_name", "render")
        image_format = task.get("image_format", "png")
        frame_padding = int(task.get("frame_padding", 4))

        width = int(task.get("width", 1280))
        height = int(task.get("height", 720))

        cmd = [
            self.maya_render_exe,

            "-r", renderer,

            "-s", str(frame_start),
            "-e", str(frame_end),
            "-b", "1",

            "-proj", project_path,
            "-rd", output_path,

            "-im", image_name,
            "-of", image_format,
            "-pad", str(frame_padding),

            # يحاول يجبر Maya يطلع الاسم بالشكل:
            # shot01.0001.png
            "-fnc", "3",

            "-cam", camera,

            "-x", str(width),
            "-y", str(height),

            scene_path,
        ]

        return cmd

    # ============================================================
    # OUTPUT NAMING FIX
    # ============================================================

    def fix_output_names(self, task, render_start_time):
        """
        Maya أحيانًا بيطلع:
            shot01.png.0001

        وإحنا عايزين:
            shot01.0001.png

        فبنصلح الاسم بعد الرندر.
        """

        print("=" * 70)
        print("FIXING MAYA OUTPUT NAMES")
        print("=" * 70)

        output_dir = Path(task["output_path"])
        scene_stem = Path(task["scene_path"]).stem

        image_name = task.get("image_name", "render")
        image_format = task.get("image_format", "png").lower().replace(".", "")
        frame_padding = int(task.get("frame_padding", 4))

        frame_start = int(task["frame_start"])
        frame_end = int(task["frame_end"])

        possible_prefixes = [
            image_name,
            scene_stem,
        ]

        final_outputs = []
        missing_outputs = []
        renamed_files = []

        for frame in range(frame_start, frame_end + 1):
            frame_padded = str(frame).zfill(frame_padding)

            correct_name = f"{image_name}.{frame_padded}.{image_format}"
            correct_path = output_dir / correct_name

            if correct_path.exists():
                print(f"Already correct: {correct_path.name}")
                final_outputs.append(str(correct_path))
                continue

            possible_wrong_names = []

            for prefix in possible_prefixes:
                possible_wrong_names.extend([
                    f"{prefix}.{image_format}.{frame_padded}",
                    f"{prefix}.{image_format}.{frame}",
                    f"{prefix}_{frame_padded}.{image_format}",
                    f"{prefix}_{frame}.{image_format}",
                    f"{prefix}.{frame}.{image_format}",
                    f"{prefix}.{frame_padded}",
                ])

            found_wrong_path = None

            for wrong_name in possible_wrong_names:
                matches = list(output_dir.rglob(wrong_name))

                for match in matches:
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

                print(
                    f"Renamed: {found_wrong_path.name} -> {correct_path.name}")

                renamed_files.append({
                    "from": str(found_wrong_path),
                    "to": str(correct_path),
                })

                final_outputs.append(str(correct_path))
            else:
                print(
                    f"Missing output for frame {frame}. Expected: {correct_name}")
                missing_outputs.append({
                    "frame": frame,
                    "expected": str(correct_path),
                })

        return {
            "final_outputs": final_outputs,
            "missing_outputs": missing_outputs,
            "renamed_files": renamed_files,
        }

    # ============================================================
    # RENDER
    # ============================================================

    def render(self, task):
        print("=" * 70)
        print("STARTING MAYA HEADLESS RENDER")
        print("=" * 70)

        self.ensure_folder(task["output_path"])

        cmd = self.build_render_command(task)

        print("Render command:")
        print(self.quote_cmd(cmd))
        print("=" * 70)

        log_path = self.get_task_log_path(task)
        render_start_time = time.time()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        render_log_lines = []

        for line in process.stdout:
            print(line, end="")
            render_log_lines.append(line)

        return_code = process.wait()
        full_log = "".join(render_log_lines)

        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(full_log)

        naming_result = self.fix_output_names(task, render_start_time)

        success = return_code == 0 and len(
            naming_result["missing_outputs"]) == 0

        print("=" * 70)
        print("Render return code:", return_code)
        print("Log path:", log_path)

        if success:
            print("RENDER SUCCESS")
        else:
            print("RENDER FAILED")

        return {
            "success": success,
            "return_code": return_code,
            "command": cmd,
            "log_path": log_path,
            "outputs": naming_result["final_outputs"],
            "missing_outputs": naming_result["missing_outputs"],
            "renamed_files": naming_result["renamed_files"],
        }

    # ============================================================
    # FULL TASK
    # ============================================================

    def run_task(self, task):
        """
        دي الدالة الوحيدة اللي worker.py هيستدعيها.
        """

        import maya.standalone

        task_result = {
            "job_id": task["job_id"],
            "task_id": task["task_id"],
            "software": "maya",
            "status": "running",
            "preflight": None,
            "render": None,
        }

        maya.standalone.initialize(name="python")

        try:
            preflight_result = self.preflight(task)
            task_result["preflight"] = preflight_result

            if preflight_result["warnings"]:
                print("=" * 70)
                print("PREFLIGHT WARNINGS")
                print("=" * 70)

                for warning in preflight_result["warnings"]:
                    print("-", warning)

            if not preflight_result["passed"]:
                print("=" * 70)
                print("PREFLIGHT FAILED")
                print("=" * 70)

                for error in preflight_result["errors"]:
                    print("-", error)

                task_result["status"] = "failed"
                return task_result

            print("=" * 70)
            print("PREFLIGHT PASSED")
            print("=" * 70)

        finally:
            maya.standalone.uninitialize()

        render_result = self.render(task)
        task_result["render"] = render_result

        if render_result["success"]:
            task_result["status"] = "done"
        else:
            task_result["status"] = "failed"

        return task_result
