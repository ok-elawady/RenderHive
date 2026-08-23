# Plugin System Architecture

## Overview

RenderHive supports submitting render jobs from multiple DCC (Digital Content Creation) tools via plugins. The plugin system is **extensible**, allowing developers to add support for new DCCs without modifying the core backend.

**Current Implementations**:

- ✅ **Maya Plugin** (v2.0.0) — Production-ready
- ❌ **Houdini Plugin** (Planned)
- ❌ **Blender Plugin** (Planned)
- ❌ **Custom DCCs** (Extensible framework)

---

## Plugin Architecture

### Generic Plugin Structure

```
plugin/
├── api/
│   ├── __init__.py
│   ├── client.py          # HTTP API wrapper
│   └── config.py          # API endpoint URLs, auth tokens
├── core/
│   ├── __init__.py
│   ├── job_builder.py     # Construct Job payload from DCC scene
│   ├── layer_mapper.py    # Map DCC layers/passes to RenderHive layers
│   └── dependency_builder.py  # Build dependency DAG
├── ui/
│   ├── __init__.py
│   ├── submitter_dialog.py  # Main submission UI
│   ├── progress_dialog.py   # Post-submission monitoring
│   └── settings_dialog.py   # Plugin configuration
├── validation/
│   ├── __init__.py
│   ├── scene_validator.py   # Validate scene before submission
│   └── rules.py             # Per-DCC validation rules
├── icons/
│   └── renderhive_logo.png
├── config/
│   └── default_config.json  # Default settings
└── README.md               # Plugin installation guide
```

### Base Plugin Class

```python
# plugin/core/base_plugin.py
from abc import ABC, abstractmethod

class BaseRenderPlugin(ABC):
    """Abstract base class for all RenderHive plugins."""

    def __init__(self, api_config: dict):
        self.api = APIClient(api_config)
        self.scene_validator = SceneValidator()

    @abstractmethod
    def get_scene_metadata(self):
        """Return DCC scene info: project, scene name, frame range."""
        pass

    @abstractmethod
    def get_render_layers(self):
        """Return list of render layers/passes in scene."""
        pass

    @abstractmethod
    def build_job_payload(self, config: dict) -> dict:
        """
        Construct RenderHive job submission payload from DCC scene.

        Args:
            config: User settings from submitter dialog
                {
                  "project": "ProjectName",
                  "priority": 75,
                  "render_layers": ["beauty", "shadow"],
                  "frame_range": [1, 100],
                  "pool_include": ["STUDIO_A"],
                  "pool_exclude": [],
                  "max_tasks_per_worker": 1
                }

        Returns:
            {
              "name": "unique-job-name",
              "visible_name": "Human-readable name",
              "project": "ProjectName",
              "priority": 75,
              "layers": [...],
              "dependencies": [...]
            }
        """
        pass

    @abstractmethod
    def validate_scene(self) -> dict:
        """
        Validate scene before submission.

        Returns:
            {
              "valid": bool,
              "warnings": ["warning1", "warning2"],
              "errors": ["error1"]
            }
        """
        pass

    def submit_job(self, job_payload: dict) -> str:
        """
        Submit job to RenderHive backend.

        Returns:
            job_id (str)
        """
        response = self.api.post('/api/jobs/', job_payload)
        return response['id']

    def show_submitter_ui(self):
        """Display job submission dialog."""
        # Implemented by subclass
        pass
```

---

## Maya Plugin Implementation

**Location**: `plugins/maya/`

### Installation (Drag-to-Install)

```python
# plugins/maya/renderhive_installer.py
import os
import platform
import shutil
import subprocess

def find_maya_path():
    """Detect Maya installation directory."""
    if platform.system() == 'Windows':
        possible_paths = [
            "C:\\Program Files\\Autodesk\\Maya2024",
            "C:\\Program Files\\Autodesk\\Maya2023",
            "C:\\Program Files\\Autodesk\\Maya2022",
        ]
    else:  # macOS/Linux
        possible_paths = [
            "/Applications/Autodesk/maya2024",
            "/opt/autodesk/maya2024",
        ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def install():
    """Auto-install plugin to Maya module directory."""
    maya_path = find_maya_path()
    if not maya_path:
        print("ERROR: Maya installation not found")
        return False

    # Create module file
    module_name = "RenderHive"
    mod_dir = os.path.join(
        os.path.expanduser("~"),
        "Maya", "modules"
    )
    os.makedirs(mod_dir, exist_ok=True)

    module_file = os.path.join(mod_dir, f"{module_name}.mod")

    # Write module definition
    mod_content = f"""+ RenderHive 2.0.0 {os.path.dirname(__file__)}
MAYA_PLUG_IN_PATH := plugins/maya/bin
PYTHONPATH := plugins/maya
"""

    with open(module_file, 'w') as f:
        f.write(mod_content)

    print(f"✓ Installed {module_name} to {module_file}")
    print("Restart Maya to load plugin")
    return True

if __name__ == '__main__':
    install()
```

**User Experience**:

```
1. Download plugin ZIP from GitHub
2. Run: renderhive_installer.exe (or .py)
3. Select Maya version
4. Click "Install"
5. Restart Maya
6. Menu: Modules → RenderHive Submitter appears
```

### Maya Plugin Entry Point

```python
# plugins/maya/renderhive_maya_submitter.py
import maya.cmds as cmds
from .ui.submitter_dialog import SubmitterDialog
from .api.config import load_config

def show_renderhive_submitter():
    """Main entry point: called from Maya menu."""
    config = load_config()
    submitter = SubmitterDialog(config)
    submitter.show()

def add_menu():
    """Add RenderHive menu to Maya main menu bar."""
    if cmds.menu("RenderHiveMenu", exists=True):
        cmds.deleteUI("RenderHiveMenu")

    menu = cmds.menu("RenderHiveMenu", label="RenderHive", tearOff=True)

    cmds.menuItem(
        label="Job Submitter",
        command=lambda: show_renderhive_submitter(),
        icon="renderhive_icon.png"
    )

    cmds.menuItem(divider=True)

    cmds.menuItem(
        label="Settings",
        command=lambda: show_settings_dialog()
    )

    cmds.menuItem(
        label="Documentation",
        command=lambda: open_browser("https://docs.renderhive.io")
    )

# Load plugin in Maya
try:
    add_menu()
    print("✓ RenderHive plugin loaded")
except Exception as e:
    print(f"✗ Failed to load RenderHive: {e}")
```

### Job Construction (Maya)

```python
# plugins/maya/core/maya_job_builder.py
import maya.cmds as cmds
from datetime import datetime

class MayaJobBuilder:
    """Convert Maya scene to RenderHive job."""

    def __init__(self):
        self.scene_path = cmds.file(q=True, sn=True)
        self.project_path = cmds.workspace(q=True, dir=True)

    def build_job_payload(self, config: dict) -> dict:
        """Construct job payload from Maya scene."""

        # Get scene metadata
        render_layers = self.get_render_layers(config['render_layers'])
        frame_range = self.get_frame_range(config)

        # Build layers
        layers = []
        for layer in render_layers:
            layer_obj = {
                "name": layer['name'],
                "type": layer['type'],  # "RENDER" or "POST"
                "order": layer['order'],
                "render_layer_name": layer.get('render_layer_name'),
                "script_path": layer.get('script_path'),
                "tasks": self.build_tasks(
                    layer,
                    frame_range,
                    config['frame_task_size']
                )
            }
            layers.append(layer_obj)

        # Build dependencies (layer-on-layer)
        dependencies = self.build_dependencies(render_layers)

        # Construct job
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_name = f"{config['project']}_{config['shot_name']}_{timestamp}"

        return {
            "name": job_name,
            "visible_name": f"{config['project']} / {config['shot_name']}",
            "project": config['project'],
            "department": config['department'],
            "user": cmds.getenv('USERNAME'),
            "priority": config['priority'],
            "max_tasks_per_worker": config['max_tasks_per_worker'],
            "log_directory": self.project_path + "/logs/",
            "layers": layers,
            "dependencies": dependencies,
            "included_pools": config.get('pool_include', []),
            "excluded_pools": config.get('pool_exclude', [])
        }

    def get_render_layers(self, selected_layers: list) -> list:
        """Get selected render layers from scene."""

        all_layers = cmds.ls(type='renderLayer')
        layers = []

        for layer_name in selected_layers:
            layer = {
                "name": layer_name,
                "type": "RENDER",
                "order": selected_layers.index(layer_name),
                "render_layer_name": layer_name
            }
            layers.append(layer)

        # Optional: post-processing layer
        if 'anim_output' in selected_layers:
            layers.append({
                "name": "anim_output",
                "type": "POST",
                "order": len(layers),
                "script_path": self.project_path + "/scripts/post_process.py"
            })

        return layers

    def get_frame_range(self, config: dict) -> tuple:
        """Get frame range from scene or user override."""
        if config.get('frame_override'):
            return (config['frame_start'], config['frame_end'])

        start = int(cmds.getAttr("defaultRenderGlobals.startFrame"))
        end = int(cmds.getAttr("defaultRenderGlobals.endFrame"))
        return (start, end)

    def build_tasks(self, layer: dict, frame_range: tuple, frame_task_size: int = 10) -> list:
        """Split frame range into tasks."""

        start, end = frame_range
        tasks = []

        for frame_start in range(start, end + 1, frame_task_size):
            frame_end = min(frame_start + frame_task_size - 1, end)
            tasks.append({
                "frame_start": frame_start,
                "frame_end": frame_end,
                "max_retries": 3 if layer['type'] == 'RENDER' else 2
            })

        return tasks

    def build_dependencies(self, layers: list) -> list:
        """Build dependency DAG (layer-on-layer)."""

        dependencies = []

        # If post-processing layer exists, make it depend on all render layers
        post_layer = next((l for l in layers if l['type'] == 'POST'), None)
        if post_layer:
            render_layers = [l for l in layers if l['type'] == 'RENDER']
            for render_layer in render_layers:
                dependencies.append({
                    "type": "LAYER_ON_LAYER",
                    "upstream_id": render_layer['uuid'],  # Would be resolved backend
                    "downstream_id": post_layer['uuid']
                })

        return dependencies
```

### Validation Engine (Maya)

```python
# plugins/maya/validation/scene_validator.py
import maya.cmds as cmds
import os

class MayaSceneValidator:
    """Validate Maya scene before RenderHive submission."""

    def validate(self, render_layers: list) -> dict:
        """Run all validation checks."""

        checks = [
            self.check_scene_saved(),
            self.check_render_layers_exist(render_layers),
            self.check_render_settings(),
            self.check_file_references(),
            self.check_memory_requirements(),
            self.check_plugin_versions(),
        ]

        warnings = [c for c in checks if c['severity'] == 'warning' and not c['passed']]
        errors = [c for c in checks if c['severity'] == 'error' and not c['passed']]

        return {
            "valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors
        }

    def check_scene_saved(self) -> dict:
        """Verify scene is saved."""
        scene_file = cmds.file(q=True, sn=True)
        passed = bool(scene_file and not cmds.file(q=True, modified=True))
        return {
            "name": "Scene Saved",
            "severity": "error",
            "passed": passed,
            "message": f"Scene: {scene_file}" if passed else "Scene not saved or has unsaved changes"
        }

    def check_render_layers_exist(self, requested_layers: list) -> dict:
        """Verify selected render layers exist in scene."""
        existing_layers = cmds.ls(type='renderLayer')
        missing = [l for l in requested_layers if l not in existing_layers]
        passed = len(missing) == 0
        return {
            "name": "Render Layers",
            "severity": "error",
            "passed": passed,
            "message": f"Found {len(requested_layers)} layers" if passed else f"Missing layers: {', '.join(missing)}"
        }

    def check_render_settings(self) -> dict:
        """Verify render settings are reasonable."""
        width = int(cmds.getAttr("defaultRenderGlobals.width"))
        height = int(cmds.getAttr("defaultRenderGlobals.height"))
        samples = int(cmds.getAttr("defaultArnoldRenderOptions.samples"))  # Arnold

        # Check bounds
        valid_res = 640 <= width <= 7680 and 480 <= height <= 4320
        valid_samples = 1 <= samples <= 10000

        passed = valid_res and valid_samples
        msg = f"Resolution: {width}x{height}, Samples: {samples}"

        return {
            "name": "Render Settings",
            "severity": "warning",
            "passed": passed,
            "message": msg if passed else f"Invalid settings: {msg}"
        }

    def check_file_references(self) -> dict:
        """Verify all file references (textures, caches) are accessible."""
        file_refs = cmds.file(q=True, reference=True)
        missing = []

        for ref in file_refs:
            ref_path = cmds.referenceQuery(ref, filename=True)
            if not os.path.exists(ref_path):
                missing.append(ref_path)

        passed = len(missing) == 0
        return {
            "name": "File References",
            "severity": "error" if missing else "warning",
            "passed": passed,
            "message": f"All {len(file_refs)} references resolved" if passed else f"Missing: {', '.join(missing[:3])}"
        }

    def check_memory_requirements(self) -> dict:
        """Estimate memory requirements and warn if excessive."""
        # Simple heuristic: check scene size
        all_nodes = cmds.ls(dag=True)
        scene_size_mb = len(all_nodes) * 0.001  # Rough estimate

        passed = scene_size_mb < 5000  # 5GB threshold
        msg = f"Estimated scene size: ~{scene_size_mb:.1f} MB"

        return {
            "name": "Memory Requirements",
            "severity": "warning",
            "passed": passed,
            "message": msg if passed else f"Very large scene: {msg}. May require high-memory workers."
        }

    def check_plugin_versions(self) -> dict:
        """Verify render plugin versions match."""
        arnold_version = cmds.getAttr("defaultArnoldRenderOptions.version")
        maya_version = cmds.about(version=True)

        # Check compatibility matrix
        compatible = self.is_version_compatible(maya_version, arnold_version)
        msg = f"Maya {maya_version}, Arnold {arnold_version}"

        return {
            "name": "Plugin Compatibility",
            "severity": "warning",
            "passed": compatible,
            "message": msg if compatible else f"Potential compatibility issue: {msg}"
        }

    @staticmethod
    def is_version_compatible(maya_version: str, arnold_version: str) -> bool:
        """Check if Maya and Arnold versions are compatible."""
        # Simplified: always compatible for now
        return True
```

### UI Dialog (Maya)

```python
# plugins/maya/ui/submitter_dialog.py
import maya.OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore

class SubmitterDialog(QtWidgets.QDialog):
    """Main job submission dialog."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.setWindowTitle("RenderHive Job Submitter")
        self.setGeometry(100, 100, 600, 800)
        self.init_ui()

    def init_ui(self):
        """Build UI layout."""
        layout = QtWidgets.QVBoxLayout()

        # Project & Shot
        project_layout = QtWidgets.QHBoxLayout()
        project_layout.addWidget(QtWidgets.QLabel("Project:"))
        self.project_input = QtWidgets.QLineEdit()
        self.project_input.setText(self.config.get('default_project', ''))
        project_layout.addWidget(self.project_input)
        layout.addLayout(project_layout)

        shot_layout = QtWidgets.QHBoxLayout()
        shot_layout.addWidget(QtWidgets.QLabel("Shot:"))
        self.shot_input = QtWidgets.QLineEdit()
        shot_layout.addWidget(self.shot_input)
        layout.addLayout(shot_layout)

        # Render Layers
        layout.addWidget(QtWidgets.QLabel("Render Layers:"))
        self.layers_list = QtWidgets.QListWidget()
        self.layers_list.setSelectionMode(QtWidgets.QAbstractItemSelectionModel.SelectionMode.MultiSelection)

        # Populate with scene layers
        for layer in self.get_scene_render_layers():
            self.layers_list.addItem(layer)

        layout.addWidget(self.layers_list)

        # Priority
        priority_layout = QtWidgets.QHBoxLayout()
        priority_layout.addWidget(QtWidgets.QLabel("Priority (1-100):"))
        self.priority_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.priority_slider.setMinimum(1)
        self.priority_slider.setMaximum(100)
        self.priority_slider.setValue(50)
        priority_layout.addWidget(self.priority_slider)
        self.priority_label = QtWidgets.QLabel("50")
        self.priority_slider.valueChanged.connect(
            lambda v: self.priority_label.setText(str(v))
        )
        priority_layout.addWidget(self.priority_label)
        layout.addLayout(priority_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.validate_btn = QtWidgets.QPushButton("Validate Scene")
        self.validate_btn.clicked.connect(self.validate_scene)
        button_layout.addWidget(self.validate_btn)

        self.submit_btn = QtWidgets.QPushButton("Submit Job")
        self.submit_btn.clicked.connect(self.submit_job)
        self.submit_btn.setEnabled(False)
        button_layout.addWidget(self.submit_btn)

        layout.addLayout(button_layout)

        # Validation Results
        self.results_text = QtWidgets.QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)

        self.setLayout(layout)

    def get_scene_render_layers(self) -> list:
        """Get available render layers from scene."""
        import maya.cmds as cmds
        return cmds.ls(type='renderLayer')

    def validate_scene(self):
        """Validate scene on button click."""
        from ..validation.scene_validator import MayaSceneValidator

        selected_layers = [
            item.text() for item in self.layers_list.selectedItems()
        ]

        validator = MayaSceneValidator()
        result = validator.validate(selected_layers)

        # Display results
        text = "VALIDATION RESULTS\n" + "=" * 50 + "\n"

        if result['valid']:
            text += "✓ PASSED: Scene is ready to submit\n\n"
            self.submit_btn.setEnabled(True)
        else:
            text += "✗ FAILED: Please fix errors before submitting\n\n"
            self.submit_btn.setEnabled(False)

        if result['errors']:
            text += "ERRORS:\n"
            for error in result['errors']:
                text += f"  ✗ {error['name']}: {error['message']}\n"
            text += "\n"

        if result['warnings']:
            text += "WARNINGS:\n"
            for warning in result['warnings']:
                text += f"  ⚠ {warning['name']}: {warning['message']}\n"

        self.results_text.setText(text)

    def submit_job(self):
        """Submit job to RenderHive backend."""
        from ..core.maya_job_builder import MayaJobBuilder
        from ..api.client import APIClient

        # Gather config
        config = {
            "project": self.project_input.text(),
            "shot_name": self.shot_input.text(),
            "priority": self.priority_slider.value(),
            "render_layers": [
                item.text() for item in self.layers_list.selectedItems()
            ],
            "frame_task_size": 10,
            "max_tasks_per_worker": 1
        }

        # Build payload
        builder = MayaJobBuilder()
        payload = builder.build_job_payload(config)

        # Submit
        api = APIClient(self.config)
        try:
            job_id = api.post('/api/jobs/', payload)['id']
            self.results_text.setText(
                f"✓ Job submitted successfully!\n\n"
                f"Job ID: {job_id}\n\n"
                f"Open dashboard to monitor: "
                f"http://localhost:3000/jobs/{job_id}"
            )
            self.submit_btn.setEnabled(False)
        except Exception as e:
            self.results_text.setText(f"✗ Submission failed: {e}")
```

---

## Extending to New DCCs

To add support for a new DCC (e.g., Houdini, Blender):

1. **Create plugin directory**:

   ```
   plugins/houdini/
   ├── core/
   ├── ui/
   ├── validation/
   └── api/
   ```

2. **Implement `BaseRenderPlugin`**:

   ```python
   class HoudiniRenderPlugin(BaseRenderPlugin):
       def get_scene_metadata(self): ...
       def get_render_layers(self): ...
       def build_job_payload(self, config): ...
       def validate_scene(self): ...
   ```

3. **Write DCC-specific validation**:

   ```python
   class HoudiniSceneValidator(SceneValidator):
       def check_rop_nodes(self): ...
       def check_hda_references(self): ...
   ```

4. **Implement UI** (using Houdini's native UI framework):

   ```python
   class HoudiniSubmitterUI:
       def __init__(self): ...
       def show(self): ...
   ```

5. **Test submission cycle**:
   - Load test scene
   - Submit job
   - Verify job appears in dashboard
   - Monitor rendering

---

## Plugin Configuration

**Config File**: `~/.renderhive/plugin_config.json`

```json
{
  "api": {
    "url": "http://localhost:8000",
    "token": "sk_live_YOUR_TOKEN"
  },
  "maya": {
    "default_project": "MyProject",
    "default_priority": 50,
    "frame_task_size": 10,
    "validation_rules": {
      "min_render_resolution": "640x480",
      "max_render_resolution": "7680x4320",
      "max_render_samples": 10000
    }
  },
  "houdini": {
    "default_priority": 50
  }
}
```

---

This plugin architecture enables **seamless** integration with any DCC while maintaining a **consistent** backend experience.
