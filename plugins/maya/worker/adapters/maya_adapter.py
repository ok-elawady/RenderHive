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
        Strong Maya/Arnold preflight before rendering.
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
        print("Requested camera:", requested_camera)

        # Frame validation
        if frame_start > frame_end:
            errors.append("frame_start is greater than frame_end.")

        if frame_start < scene_start or frame_end > scene_end:
            warnings.append(
                "Requested frame range is outside the scene render range. "
                "Command line render may still work because it overrides scene settings."
            )

        # Arnold validation
        arnold_check = self.check_arnold_environment(requested_renderer)
        errors.extend(arnold_check["errors"])
        warnings.extend(arnold_check["warnings"])

        # Camera validation
        camera_check = self.check_camera_validity(requested_camera)
        errors.extend(camera_check["errors"])
        warnings.extend(camera_check["warnings"])

        # Output validation
        output_check = self.check_output_settings(task)
        errors.extend(output_check["errors"])
        warnings.extend(output_check["warnings"])

        # Missing textures validation
        texture_check = self.check_missing_textures(task)
        errors.extend(texture_check["errors"])
        warnings.extend(texture_check["warnings"])

        # Side plugins warning
        side_plugin_check = self.check_side_plugins()
        warnings.extend(side_plugin_check["warnings"])

        print("Available cameras:", camera_check.get("available_cameras", []))
        print("mtoa loaded:", arnold_check.get("mtoa_loaded"))
        print("mtoa path:", arnold_check.get("mtoa_path"))
        print("Checked textures:", len(texture_check.get("checked_textures", [])))
        print("Missing textures:", len(texture_check.get("missing_textures", [])))
        print("Side plugins:", side_plugin_check.get("side_plugins", []))

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,

            "scene_renderer": current_renderer,
            "scene_frame_start": scene_start,
            "scene_frame_end": scene_end,

            "arnold_check": arnold_check,
            "camera_check": camera_check,
            "output_check": output_check,
            "texture_check": texture_check,
            "side_plugin_check": side_plugin_check,
        }

    def check_arnold_environment(self, requested_renderer):
        """
        Checks Arnold plugin availability and renderer setup.
        """

        import maya.cmds as cmds

        errors = []
        warnings = []

        requested_renderer = requested_renderer.lower()

        arnold_loaded = False
        arnold_path = None

        try:
            arnold_loaded = cmds.pluginInfo("mtoa", query=True, loaded=True)
        except Exception:
            arnold_loaded = False

        if not arnold_loaded:
            try:
                cmds.loadPlugin("mtoa")
                arnold_loaded = True
                warnings.append(
                    "mtoa plugin was not loaded, RenderHive loaded it automatically.")
            except Exception as e:
                arnold_loaded = False
                if requested_renderer == "arnold":
                    errors.append(
                        "Arnold plugin mtoa is not loaded and could not be loaded: {}".format(e))

        try:
            arnold_path = cmds.pluginInfo("mtoa", query=True, path=True)
        except Exception:
            arnold_path = "Not found"

        try:
            current_renderer = cmds.getAttr(
                "defaultRenderGlobals.currentRenderer")
        except Exception:
            current_renderer = "unknown"

        if requested_renderer == "arnold":
            if current_renderer != "arnold":
                warnings.append(
                    "Scene renderer is '{}', but task renderer is Arnold. Command line render will override it.".format(
                        current_renderer
                    )
                )
        else:
            warnings.append(
                "Task renderer is '{}'. Arnold validation is limited because this task is not using Arnold.".format(
                    requested_renderer
                )
            )

        return {
            "errors": errors,
            "warnings": warnings,
            "mtoa_loaded": arnold_loaded,
            "mtoa_path": arnold_path,
            "scene_renderer": current_renderer,
        }

    def check_camera_validity(self, requested_camera):
        """
        Checks if the requested camera exists and is a valid camera transform.
        """

        import maya.cmds as cmds

        errors = []
        warnings = []

        camera_shapes = cmds.ls(type="camera") or []
        camera_names = []

        for cam_shape in camera_shapes:
            parents = cmds.listRelatives(cam_shape, parent=True) or []
            if parents:
                camera_names.append(parents[0])

        if requested_camera not in camera_names:
            errors.append(
                "Camera '{}' does not exist. Available cameras: {}".format(
                    requested_camera,
                    camera_names
                )
            )
            return {
                "errors": errors,
                "warnings": warnings,
                "available_cameras": camera_names,
                "camera_shape": None,
                "is_renderable": False,
            }

        shapes = cmds.listRelatives(
            requested_camera, shapes=True, type="camera") or []

        if not shapes:
            errors.append(
                "'{}' exists but has no camera shape.".format(requested_camera))
            return {
                "errors": errors,
                "warnings": warnings,
                "available_cameras": camera_names,
                "camera_shape": None,
                "is_renderable": False,
            }

        camera_shape = shapes[0]

        try:
            is_renderable = cmds.getAttr(camera_shape + ".renderable")
        except Exception:
            is_renderable = False

        if requested_camera in ["persp", "top", "front", "side"]:
            warnings.append(
                "Requested camera '{}' is a default Maya camera. For production, use a dedicated render camera like renderCam.".format(
                    requested_camera
                )
            )

        if not is_renderable:
            warnings.append(
                "Camera '{}' exists but is not marked as renderable. Command line render may still use it because -cam is provided.".format(
                    requested_camera
                )
            )

        return {
            "errors": errors,
            "warnings": warnings,
            "available_cameras": camera_names,
            "camera_shape": camera_shape,
            "is_renderable": is_renderable,
        }

    def check_output_settings(self, task):
        """
        Validates output format, image name, frame padding and output path.
        """

        errors = []
        warnings = []

        output_path = task["output_path"]
        image_name = task.get("image_name", "render")
        image_format = task.get("image_format", "png").lower().replace(".", "")
        frame_padding = int(task.get("frame_padding", 4))
        renderer = task.get("renderer", "arnold").lower()

        allowed_arnold_formats = [
            "exr",
            "png",
            "jpg",
            "jpeg",
            "tif",
            "tiff"
        ]

        if renderer == "arnold" and image_format not in allowed_arnold_formats:
            errors.append(
                "Unsupported image format for Arnold: '{}'. Allowed formats: {}".format(
                    image_format,
                    allowed_arnold_formats
                )
            )

        if not image_name:
            errors.append("Image name is empty.")

        if frame_padding < 1:
            errors.append("Frame padding must be at least 1.")

        if not output_path:
            errors.append("Output path is empty.")
        else:
            try:
                self.ensure_folder(output_path)
            except Exception as e:
                errors.append(
                    "Could not create output path '{}': {}".format(output_path, e))

        if " " in image_name:
            warnings.append(
                "Image name contains spaces. RenderHive will still work, but underscores are recommended."
            )

        return {
            "errors": errors,
            "warnings": warnings,
            "image_format": image_format,
            "output_path": output_path,
        }

    def get_texture_search_folders(self, project_path, scene_path):
        """
        Common Maya texture folders.
        """

        import os

        folders = []

        if project_path:
            folders.extend([
                project_path,
                os.path.join(project_path, "sourceimages"),
                os.path.join(project_path, "images"),
                os.path.join(project_path, "textures"),
                os.path.join(project_path, "tex"),
            ])

        if scene_path:
            scene_dir = os.path.dirname(scene_path)
            folders.extend([
                scene_dir,
                os.path.join(scene_dir, "sourceimages"),
                os.path.join(scene_dir, "..", "sourceimages"),
                os.path.join(scene_dir, "..", "textures"),
                os.path.join(scene_dir, "..", "tex"),
            ])

        clean_folders = []

        for folder in folders:
            folder = os.path.abspath(folder)

            if folder not in clean_folders and os.path.exists(folder):
                clean_folders.append(folder)

        return clean_folders

    def resolve_texture_path(self, texture_path, project_path=None, scene_path=None):
        """
        Resolves:
        - absolute paths
        - environment variables
        - Maya workspace-relative paths
        - filename-only paths by searching sourceimages/textures folders
        """

        import os
        import glob
        import maya.cmds as cmds

        if not texture_path:
            return ""

        original_path = texture_path
        path = os.path.expandvars(texture_path)
        path = path.replace("\\", "/")

        # 1. Direct absolute path
        if os.path.isabs(path) and os.path.exists(path):
            return path

        # 2. Maya workspace expansion
        try:
            expanded = cmds.workspace(expandName=path)
            if expanded and os.path.exists(expanded):
                return expanded.replace("\\", "/")
        except Exception:
            pass

        # 3. Search common project folders
        basename = os.path.basename(path)
        search_folders = self.get_texture_search_folders(
            project_path, scene_path)

        for folder in search_folders:
            direct_candidate = os.path.join(folder, basename)

            if os.path.exists(direct_candidate):
                return direct_candidate.replace("\\", "/")

        # 4. Recursive search inside common folders
        for folder in search_folders:
            pattern = os.path.join(folder, "**", basename)
            matches = glob.glob(pattern, recursive=True)

            if matches:
                return matches[0].replace("\\", "/")

        # fallback
        return original_path

    def texture_path_exists(self, texture_path, project_path=None, scene_path=None):
        """
        Supports normal paths, filename-only paths, UDIM paths and sequence paths.
        """

        import os
        import glob
        import re

        if not texture_path:
            return False

        resolved = self.resolve_texture_path(
            texture_path,
            project_path=project_path,
            scene_path=scene_path
        )

        if os.path.exists(resolved):
            return True

        patterns = []

        patterns.extend([
            resolved.replace("<UDIM>", "*"),
            resolved.replace("<udim>", "*"),
            resolved.replace("%(UDIM)d", "*"),
        ])

        if "#" in resolved:
            patterns.append(re.sub(r"#+", "*", resolved))

        for pattern in patterns:
            if pattern != resolved and glob.glob(pattern):
                return True

        return False

    def check_missing_textures(self, task):
        """
        Checks Maya file nodes and Arnold aiImage nodes for missing textures.
        Also resolves filename-only paths by searching project sourceimages/textures.
        """

        import maya.cmds as cmds

        project_path = task.get("project_path")
        scene_path = task.get("scene_path")

        checked_textures = []
        missing_textures = []

        texture_nodes = []

        file_nodes = cmds.ls(type="file") or []
        for node in file_nodes:
            texture_nodes.append((node, "fileTextureName", "file"))

        ai_image_nodes = cmds.ls(type="aiImage") or []
        for node in ai_image_nodes:
            texture_nodes.append((node, "filename", "aiImage"))

        for node, attr_name, node_type in texture_nodes:
            attr = node + "." + attr_name

            if not cmds.objExists(attr):
                continue

            texture_path = cmds.getAttr(attr)

            if not texture_path:
                continue

            resolved_path = self.resolve_texture_path(
                texture_path,
                project_path=project_path,
                scene_path=scene_path
            )

            exists = self.texture_path_exists(
                texture_path,
                project_path=project_path,
                scene_path=scene_path
            )

            item = {
                "node": node,
                "type": node_type,
                "path": texture_path,
                "resolved_path": resolved_path,
                "exists": exists,
            }

            checked_textures.append(item)

            if not exists:
                missing_textures.append(item)

        errors = []

        for missing in missing_textures:
            errors.append(
                "Missing texture on node '{}': {} | resolved: {}".format(
                    missing["node"],
                    missing["path"],
                    missing["resolved_path"]
                )
            )

        return {
            "errors": errors,
            "warnings": [],
            "checked_textures": checked_textures,
            "missing_textures": missing_textures,
        }

    def check_side_plugins(self):
        """
        Detects non-render side plugins that may slow or pollute headless rendering.
        This is warning-only for now.
        """

        import maya.cmds as cmds

        warnings = []
        found_side_plugins = []

        loaded_plugins = cmds.pluginInfo(query=True, listPlugins=True) or []

        side_keywords = [
            "zoo",
            "mgear",
            "ngskintools",
            "redshift",
            "vray",
            "renderman",
            "yeti"
        ]

        for plugin in loaded_plugins:
            low = plugin.lower()

            for keyword in side_keywords:
                if keyword in low:
                    found_side_plugins.append(plugin)

        if found_side_plugins:
            warnings.append(
                "Potential side plugins loaded: {}. Clean Worker Mode should reduce this later.".format(
                    found_side_plugins
                )
            )

        return {
            "warnings": warnings,
            "loaded_plugins": loaded_plugins,
            "side_plugins": found_side_plugins,
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
