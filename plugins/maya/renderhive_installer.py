from __future__ import print_function

import datetime
import json
import os
import shutil
import sys
import tempfile

import maya.cmds as cmds
import maya.mel as mel



SHELF_NAME = "RenderHive"
BUTTON_ANNOTATION = "Open RenderHive Maya Submitter"
MAIN_MENU_NAME = "RenderHiveMainMenu"
MAIN_MENU_LABEL = "RenderHive"
STARTUP_BLOCK_BEGIN = "# >>> RenderHive Maya startup >>>"
STARTUP_BLOCK_END = "# <<< RenderHive Maya startup <<<"


def get_installed_package_dir():
    return os.path.join(
        cmds.internalVar(
            userScriptDir=True
        ),
        "RenderHive"
    )


def _ignore_runtime_content(
    directory,
    names,
):
    ignored = []

    ignored_names = {
        "__pycache__",
        ".git",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "backup",
        "backups",
        "logs",
        "reports",
        "tests",
        "tools",
        "contracts",
    }

    for name in names:
        lowered = name.lower()

        if (
            name in ignored_names
            or lowered.startswith("backup_")
            or lowered.endswith(".zip")
            or lowered.endswith(".pyc")
            or lowered.endswith(".md")
            or lowered.endswith(".yaml")
            or lowered.endswith(".yml")
        ):
            ignored.append(
                name
            )

    return ignored


def _validate_staged_package(path):
    required = (
        "renderhive_maya_submitter.py",
        os.path.join("api", "version.py"),
        os.path.join("ui", "qt_submitter_window.py"),
        os.path.join("ui", "common_widgets.py"),
        os.path.join("ui", "font_loader.py"),
        os.path.join("ui", "icons.py"),
        os.path.join("ui", "targeting_widgets.py"),
        os.path.join("ui", "icons", "check_mark.png"),
        os.path.join("ui", "worker_data.py"),
        os.path.join("ui", "runtime_registry.py"),
        os.path.join("ui", "controllers", "__init__.py"),
        os.path.join("ui", "controllers", "api_controller.py"),
        os.path.join("ui", "controllers", "targeting_controller.py"),
        os.path.join("ui", "controllers", "dependency_controller.py"),
        os.path.join("ui", "job_dependency_widgets.py"),
        os.path.join("submission", "__init__.py"),
        os.path.join("submission", "task_builder.py"),
        os.path.join("submission", "task_validation.py"),
        os.path.join("ui", "pages", "job_page.py"),
        os.path.join("ui", "pages", "render_page.py"),
        os.path.join("ui", "pages", "validation_page.py"),
        os.path.join("ui", "pages", "tools_page.py"),
        os.path.join("validation", "validator.py"),
        os.path.join("validation", "submission_checks.py"),
    )
    missing = [item for item in required if not os.path.isfile(os.path.join(path, item))]
    if missing:
        raise RuntimeError("Installer package is incomplete: {}".format(", ".join(missing)))


def copy_package_to_maya_scripts(source_dir):
    install_dir = get_installed_package_dir()
    parent = os.path.dirname(install_dir)
    if not os.path.isdir(parent):
        os.makedirs(parent)

    stage_dir = tempfile.mkdtemp(prefix="RenderHive_stage_", dir=parent)
    backup_dir = ""
    try:
        shutil.rmtree(stage_dir)
        shutil.copytree(source_dir, stage_dir, ignore=_ignore_runtime_content)
        _validate_staged_package(stage_dir)

        if os.path.isdir(install_dir):
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = "{}_backup_{}".format(install_dir, stamp)
            os.replace(install_dir, backup_dir)

        os.replace(stage_dir, install_dir)
        _validate_staged_package(install_dir)
        return install_dir
    except Exception:
        if os.path.isdir(install_dir):
            shutil.rmtree(install_dir, ignore_errors=True)
        if backup_dir and os.path.isdir(backup_dir):
            os.replace(backup_dir, install_dir)
        raise
    finally:
        if os.path.isdir(stage_dir):
            shutil.rmtree(stage_dir, ignore_errors=True)


def get_shelf_top_level():
    return mel.eval(
        "$tmp = $gShelfTopLevel"
    )


def _python_open_command(install_dir):
    return r"""
import importlib
import os
import sys

renderhive_path = r"{install_dir}"
if renderhive_path in sys.path:
    sys.path.remove(renderhive_path)
sys.path.insert(0, renderhive_path)

modules_to_remove = []
_normalized_path = renderhive_path.replace("\\\\", "/").replace("\\", "/").lower()
for mod_name, mod in list(sys.modules.items()):
    _mod_file = getattr(mod, "__file__", "") or ""
    _mod_file = _mod_file.replace("\\\\", "/").replace("\\", "/").lower()
    if _normalized_path in _mod_file:
        modules_to_remove.append(mod_name)
    elif mod_name.startswith("renderhive_"):
        modules_to_remove.append(mod_name)
for mod_name in modules_to_remove:
    try:
        del sys.modules[mod_name]
    except KeyError:
        pass

import renderhive_maya_submitter
renderhive_maya_submitter.show_submitter()
""".format(
        install_dir=str(install_dir).replace("\\", "\\\\")
    )


def _python_validate_command(install_dir):
    return r"""
import importlib
import os
import sys

renderhive_path = r"{install_dir}"
if renderhive_path in sys.path:
    sys.path.remove(renderhive_path)
sys.path.insert(0, renderhive_path)

modules_to_remove = []
_normalized_path = renderhive_path.replace("\\\\", "/").replace("\\", "/").lower()
for mod_name, mod in list(sys.modules.items()):
    _mod_file = getattr(mod, "__file__", "") or ""
    _mod_file = _mod_file.replace("\\\\", "/").replace("\\", "/").lower()
    if _normalized_path in _mod_file:
        modules_to_remove.append(mod_name)
    elif mod_name.startswith("renderhive_"):
        modules_to_remove.append(mod_name)
for mod_name in modules_to_remove:
    try:
        del sys.modules[mod_name]
    except KeyError:
        pass

import renderhive_maya_submitter
renderhive_maya_submitter.show_submitter()
renderhive_maya_submitter.validate_scene_from_ui()
""".format(
        install_dir=str(install_dir).replace("\\", "\\\\")
    )


def remove_main_menu():
    try:
        if cmds.menu(MAIN_MENU_NAME, exists=True):
            cmds.deleteUI(MAIN_MENU_NAME, menu=True)
    except Exception:
        pass


def ensure_main_menu(install_dir=None):
    if not install_dir:
        install_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        install_dir = os.path.abspath(install_dir)

    remove_main_menu()

    try:
        main_window = mel.eval("$tmp = $gMainWindow")
        menu = cmds.menu(
            MAIN_MENU_NAME,
            label=MAIN_MENU_LABEL,
            parent=main_window,
            tearOff=False,
        )

        cmds.menuItem(
            parent=menu,
            label="Open RenderHive",
            annotation="Open the RenderHive Maya Submitter",
            sourceType="python",
            command=_python_open_command(install_dir),
        )
        cmds.menuItem(
            parent=menu,
            label="Validate Current Scene",
            annotation="Open RenderHive and validate the current Maya scene",
            sourceType="python",
            command=_python_validate_command(install_dir),
        )
        cmds.menuItem(parent=menu, divider=True)
        cmds.menuItem(
            parent=menu,
            label="Uninstall RenderHive",
            annotation="Remove RenderHive from this Maya installation",
            sourceType="python",
            command=(
                "import renderhive_maya_submitter; "
                "renderhive_maya_submitter.uninstall_renderhive_from_maya()"
            ),
        )
        return menu
    except Exception:
        return None


def _startup_block(install_dir):
    safe_path = repr(os.path.abspath(install_dir))
    return """{begin}
try:
    import maya.utils as _renderhive_maya_utils

    def _renderhive_install_menu():
        import importlib
        import sys
        _renderhive_path = {path}
        if _renderhive_path in sys.path:
            sys.path.remove(_renderhive_path)
        sys.path.insert(0, _renderhive_path)
        import renderhive_installer
        renderhive_installer.ensure_main_menu(_renderhive_path)

    _renderhive_maya_utils.executeDeferred(_renderhive_install_menu)
except Exception:
    pass
{end}
""".format(
        begin=STARTUP_BLOCK_BEGIN,
        end=STARTUP_BLOCK_END,
        path=safe_path,
    )


def _remove_startup_block(content):
    start = content.find(STARTUP_BLOCK_BEGIN)
    if start < 0:
        return content

    end = content.find(STARTUP_BLOCK_END, start)
    if end < 0:
        return content[:start].rstrip() + "\n"

    end += len(STARTUP_BLOCK_END)
    return (content[:start] + content[end:]).strip() + "\n"


def get_user_setup_path():
    return os.path.join(
        cmds.internalVar(userScriptDir=True),
        "userSetup.py",
    )


def install_startup_hook(install_dir):
    path = get_user_setup_path()
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)

    content = ""
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except Exception:
            content = ""

    content = _remove_startup_block(content).rstrip()
    if content:
        content += "\n\n"
    content += _startup_block(install_dir)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)

    return path


def remove_startup_hook():
    path = get_user_setup_path()
    if not os.path.isfile(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        updated = _remove_startup_block(content)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(updated)
        return True
    except Exception:
        return False


def ensure_shelf():
    shelf_top = get_shelf_top_level()
    try:
        shelves = cmds.tabLayout(
            shelf_top,
            query=True,
            childArray=True
        ) or []
    except Exception:
        shelves = []

    if SHELF_NAME not in shelves:
        try:
            mel.eval('addNewShelfTab("%s");' % SHELF_NAME)
        except Exception:
            try:
                cmds.shelfLayout(
                    SHELF_NAME,
                    parent=shelf_top
                )
            except Exception:
                pass

    try:
        cmds.tabLayout(
            shelf_top,
            edit=True,
            selectTab=SHELF_NAME
        )
    except Exception:
        pass

    return SHELF_NAME


def _is_renderhive_button(
    button
):
    values = []

    for flag in (
        "label",
        "annotation",
        "command",
    ):
        try:
            values.append(
                cmds.shelfButton(
                    button,
                    query=True,
                    **{flag: True}
                ) or ""
            )
        except Exception:
            pass

    return "renderhive" in " ".join(
        str(value)
        for value in values
    ).lower()


def remove_renderhive_shelf_buttons(delete_shelf_tab=False):
    try:
        shelf_top = get_shelf_top_level()
        shelves = cmds.tabLayout(
            shelf_top,
            query=True,
            childArray=True
        ) or []

        for shelf_name in shelves:
            try:
                children = cmds.shelfLayout(
                    shelf_name,
                    query=True,
                    childArray=True
                ) or []

                for child in children:
                    if _is_renderhive_button(
                        child
                    ):
                        try:
                            cmds.deleteUI(
                                child
                            )
                        except Exception:
                            pass
            except Exception:
                pass

        if delete_shelf_tab:
            # If the RenderHive shelf tab layout exists, delete the shelf tab itself
            if cmds.shelfLayout(SHELF_NAME, exists=True):
                cmds.deleteUI(SHELF_NAME, layout=True)

        try:
            mel.eval(
                "saveAllShelves $gShelfTopLevel;"
            )
        except Exception:
            pass

    except Exception:
        pass


def create_shelf_button(
    install_dir
):
    try:
        shelf_name = ensure_shelf()

        # Check if a RenderHive button already exists in the shelf
        children = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
        for child in children:
            if _is_renderhive_button(child):
                return

        icon_path = os.path.join(
            install_dir,
            "icons",
            "renderhive_shelf_icon.png"
        ).replace(
            "\\",
            "/"
        )

        cmds.shelfButton(
            parent=shelf_name,
            label="RenderHive",
            annotation=BUTTON_ANNOTATION,
            image=icon_path,
            image1=icon_path,
            imageOverlayLabel="",
            style="iconOnly",
            sourceType="python",
            command=_python_open_command(install_dir),
        )

        try:
            mel.eval(
                "saveAllShelves $gShelfTopLevel;"
            )
        except Exception:
            pass
    except Exception:
        pass


def write_install_info(
    install_dir,
    source_dir,
):
    try:
        from api.version import PLUGIN_VERSION
    except ImportError:
        PLUGIN_VERSION = "Unknown"

    info_path = os.path.join(
        install_dir,
        "renderhive_install_info.json"
    )

    with open(
        info_path,
        "w",
        encoding="utf-8"
    ) as handle:
        json.dump(
            {
                "source_dir": os.path.abspath(
                    source_dir
                ),
                "install_dir": os.path.abspath(
                    install_dir
                ),
                "plugin_version": PLUGIN_VERSION,
            },
            handle,
            indent=4,
        )

    return info_path


def install_from_drag_drop(
    source_dir
):
    try:
        from api.version import PLUGIN_VERSION
    except ImportError:
        PLUGIN_VERSION = "Unknown"

    install_dir = copy_package_to_maya_scripts(
        source_dir
    )
    write_install_info(
        install_dir,
        source_dir
    )
    create_shelf_button(
        install_dir
    )
    install_startup_hook(install_dir)
    ensure_main_menu(install_dir)

    cmds.confirmDialog(
        title="RenderHive Installed",
        message=(
            "RenderHive v{} was installed successfully.\n\n"
            "Installed to:\n{}\n\n"
            "A RenderHive shelf button and main-menu entry were created."
        ).format(
            PLUGIN_VERSION,
            install_dir
        ),
        button=["OK"],
        icon="information",
    )


def close_renderhive_windows():
    try:
        from ui.qt_compat import QtWidgets

        app = QtWidgets.QApplication.instance()

        if app is not None:
            for widget in app.topLevelWidgets():
                if widget.objectName() in (
                    "RenderHiveWindow",
                    "RenderHiveQtSubmitter",
                ):
                    widget.close()
                    widget.deleteLater()
    except Exception:
        pass

    try:
        if cmds.window(
            "renderHiveMayaSubmitter",
            exists=True
        ):
            cmds.deleteUI(
                "renderHiveMayaSubmitter"
            )
    except Exception:
        pass


def uninstall_renderhive(
    confirm=True
):
    versioned_dir = get_installed_package_dir()
    script_parent = os.path.dirname(cmds.internalVar(userScriptDir=True).rstrip("/\\"))
    global_dir = os.path.join(os.path.dirname(script_parent), "scripts", "RenderHive")
    current_pkg_dir = os.path.dirname(os.path.abspath(__file__))

    candidate_dirs = [versioned_dir, global_dir]
    if "RenderHive" in current_pkg_dir:
        candidate_dirs.append(current_pkg_dir)

    target_display = versioned_dir if os.path.isdir(versioned_dir) else (global_dir if os.path.isdir(global_dir) else versioned_dir)

    if confirm:
        result = cmds.confirmDialog(
            title="Uninstall RenderHive",
            message=(
                "Remove the RenderHive shelf button and installed Maya copy?\n\n"
                "{}\n\n"
                "The original source package will not be deleted."
            ).format(
                target_display
            ),
            button=["Uninstall", "Cancel"],
            defaultButton="Cancel",
            cancelButton="Cancel",
            dismissString="Cancel",
            icon="warning",
        )

        if result != "Uninstall":
            return False

    close_renderhive_windows()
    remove_renderhive_shelf_buttons(delete_shelf_tab=True)
    remove_main_menu()
    remove_startup_hook()

    # Remove startup hook from global scripts directory as well
    global_user_setup = os.path.join(os.path.dirname(script_parent), "scripts", "userSetup.py")
    if os.path.isfile(global_user_setup):
        try:
            with open(global_user_setup, "r", encoding="utf-8") as handle:
                content = handle.read()
            updated = _remove_startup_block(content)
            with open(global_user_setup, "w", encoding="utf-8") as handle:
                handle.write(updated)
        except Exception:
            pass

    # Delete shelf_RenderHive.mel from prefs
    try:
        shelf_file = os.path.join(cmds.internalVar(userPrefDir=True), "shelves", "shelf_RenderHive.mel")
        if os.path.isfile(shelf_file):
            os.remove(shelf_file)
    except Exception:
        pass

    # Delete RenderHive.mod module files
    try:
        maya_parent = os.path.dirname(script_parent)
        mod_candidates = [
            os.path.join(maya_parent, "modules", "RenderHive.mod"),
            os.path.join(cmds.internalVar(userPrefDir=True), "..", "modules", "RenderHive.mod"),
        ]
        for mod_path in mod_candidates:
            if os.path.isfile(mod_path):
                try:
                    os.remove(mod_path)
                except Exception:
                    pass
    except Exception:
        pass

    # Remove all candidate install directories
    for directory in set(candidate_dirs):
        if os.path.isdir(directory):
            try:
                shutil.rmtree(directory, ignore_errors=True)
            except Exception:
                pass
        
    # Clear the plugin from Maya's python memory cache
    import sys
    modules_to_remove = []
    for mod_name, mod in list(sys.modules.items()):
        _mod_file = (getattr(mod, "__file__", "") or "").replace("\\\\", "/").replace("\\", "/").lower()
        if "renderhive" in _mod_file or mod_name.startswith("renderhive_") or mod_name.startswith("renderhive.") or mod_name == "renderhive":
            modules_to_remove.append(mod_name)
            
    for mod_name in modules_to_remove:
        try:
            del sys.modules[mod_name]
        except KeyError:
            pass

    cmds.confirmDialog(
        title="RenderHive Uninstalled",
        message=(
            "RenderHive was removed from Maya.\n\n"
            "Restart Maya if the shelf still appears."
        ),
        button=["OK"],
        icon="information",
    )

    return True


def onMayaDroppedPythonFile(dropFile):
    """
    Called by Maya when this python file is dragged and dropped into the viewport.
    """
    import sys
    import os
    
    source_dir = os.path.dirname(os.path.abspath(dropFile))
    if source_dir not in sys.path:
        sys.path.insert(0, source_dir)
        
    # Now that sys.path has the source dir, we can install
    install_from_drag_drop(source_dir)
