"""ROP and Solaris render-node discovery for Houdini 19.5+.

Discovery remains deliberately lightweight. Detailed camera, renderer and USD
Render Product inspection happens only after an artist selects a render node.
"""

from __future__ import absolute_import

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderNodeInfo:
    path: str
    name: str
    type_name: str
    type_label: str
    category: str
    renderer: str
    execution_mode: str
    frame_start: float
    frame_end: float
    frame_step: float
    frame_source: str
    camera: str
    output_path: str
    resolution_width: int
    resolution_height: int
    is_bypassed: bool
    is_locked: bool
    is_renderable: bool
    available_cameras: tuple = ()
    available_renderers: tuple = ()
    usd_output_path: str = ""
    output_source: str = "render_node"
    details_loaded: bool = True
    camera_override: bool = False
    renderer_override: bool = False
    output_override: bool = False
    resolution_override: bool = False

    @property
    def display_label(self):
        return "{}  —  {}  ({})".format(
            self.path,
            self.renderer,
            self.type_label or self.type_name,
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

_USD_OUTPUT_PARMS = (
    "lopoutput",
    "usdfile",
    "usd_file",
    "filename",
)

_GENERIC_OUTPUT_PARMS = _IMAGE_OUTPUT_PARMS + _USD_OUTPUT_PARMS + (
    "sopoutput",
    "file",
)

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

_RENDER_SETTINGS_PARMS = (
    "rendersettings",
    "render_settings",
    "rendersettingsprim",
    "render_settings_prim",
    "settingsprim",
)

_SOLARIS_EXECUTABLE_TYPES = {
    "usdrender_rop",
    "usd_render_rop",
    "usd_rop",
    "karmarender",
    "karmarender_rop",
}

_SETTINGS_ONLY_MARKERS = (
    "rendersettings",
    "render_settings",
)


def _node_type_name(node):
    try:
        return str(node.type().name() or "")
    except Exception:
        return ""


def _node_type_label(node):
    try:
        description = node.type().description()
        if description:
            return str(description)
    except Exception:
        pass
    return _node_type_name(node)


def _category_name(node):
    try:
        category = node.type().category()
        return str(category.name() or "")
    except Exception:
        return ""


def _parm(node, name):
    try:
        return node.parm(name)
    except Exception:
        return None


def _eval_parm(node, names, default=""):
    for name in names:
        parm = _parm(node, name)
        if parm is None:
            continue
        try:
            value = parm.eval()
        except Exception:
            try:
                value = parm.evalAsString()
            except Exception:
                continue
        if value not in (None, ""):
            return value
    return default


def _eval_number(node, names, default=0.0):
    value = _eval_parm(node, names, default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _bool_method(node, method_name):
    try:
        method = getattr(node, method_name)
        return bool(method())
    except Exception:
        return False


def _has_any_parm(node, names):
    return any(_parm(node, name) is not None for name in names)


def _unique(values):
    result = []
    for value in values or []:
        value = str(value or "").strip()
        if value and value not in result:
            result.append(value)
    return result


def _renderer_label(value):
    value = str(value or "").strip()
    lower = value.lower().replace("_", " ")
    combined = "{} {}".format(value, lower)
    if "karma" in lower:
        if "xpu" in lower:
            return "Karma XPU"
        if "cpu" in lower:
            return "Karma CPU"
        return "Karma"
    if "arnold" in lower:
        return "Arnold"
    if "redshift" in lower or lower.startswith("rs "):
        return "Redshift"
    if "mantra" in lower or lower in ("ifd", "vm"):
        return "Mantra"
    if "renderman" in lower or "prman" in lower:
        return "RenderMan"
    if "vray" in lower or "v ray" in lower:
        return "V-Ray"
    if "octane" in lower:
        return "Octane"
    if "usd render" in lower or "usdrender" in lower:
        return "USD Render"
    return value


def _parm_menu_labels(node, names):
    values = []
    for name in names:
        parm = _parm(node, name)
        if parm is None:
            continue
        try:
            labels = list(parm.menuLabels())
        except Exception:
            labels = []
        try:
            items = list(parm.menuItems())
        except Exception:
            items = []
        source = labels or items
        for value in source:
            label = _renderer_label(value)
            if label:
                values.append(label)
    return _unique(values)


def is_supported_render_node(node):
    """Return True for executable ROPs and executable Solaris render nodes."""
    if node is None:
        return False

    type_name = _node_type_name(node).lower()
    category = _category_name(node).lower()

    if category in ("driver", "rop"):
        return True

    if type_name in _SOLARIS_EXECUTABLE_TYPES:
        return True

    if any(marker in type_name for marker in ("usdrender_rop", "karmarender_rop")):
        return True

    if category == "lop":
        if any(marker in type_name for marker in _SETTINGS_ONLY_MARKERS):
            return False
        has_action = _has_any_parm(node, ("execute", "render", "executegraph"))
        has_output = _has_any_parm(node, _GENERIC_OUTPUT_PARMS)
        return bool(has_action and has_output)

    return False


def renderer_for_node(node, evaluate_parameters=True):
    type_name = _node_type_name(node).lower()
    explicit = (
        str(_eval_parm(node, _RENDERER_PARMS, "") or "").strip()
        if evaluate_parameters
        else ""
    )
    combined = "{} {}".format(type_name, explicit.lower())
    label = _renderer_label(combined)
    if label and label != combined:
        return label
    if "geometry" in combined or type_name in ("rop_geometry", "geometry"):
        return "Geometry Cache"
    if "alembic" in combined:
        return "Alembic"
    if "usdrender" in combined or "usd_render" in combined:
        return _renderer_label(explicit) or "USD Render"
    return _renderer_label(explicit) or _node_type_label(node) or "Houdini ROP"


def available_renderers_for_node(node, current_renderer=""):
    values = []
    current = _renderer_label(current_renderer)
    if current:
        values.append(current)
    values.extend(_parm_menu_labels(node, _RENDERER_PARMS))

    type_name = _node_type_name(node).lower()
    if "karma" in type_name or "usdrender" in type_name or "usd_render" in type_name:
        values.extend(("Karma CPU", "Karma XPU"))
    return tuple(_unique(values))


def execution_mode_for_node(node):
    type_name = _node_type_name(node).lower()
    category = _category_name(node).lower()
    if "usdrender" in type_name or "karmarender" in type_name:
        return "husk"
    if category == "lop" and "usd" in type_name:
        return "husk"
    return "hython"


def _scene_frame_range():
    try:
        import hou
        start, end = hou.playbar.frameRange()
        return float(start), float(end), 1.0
    except Exception:
        return 1.0, 240.0, 1.0


def frame_range_for_node(node, scene_range=None):
    scene_start, scene_end, scene_step = scene_range or _scene_frame_range()
    trange = int(_eval_number(node, ("trange",), 1))

    if trange == 0:
        try:
            import hou
            current = float(hou.frame())
        except Exception:
            current = scene_start
        return current, current, 1.0, "Current Frame"

    has_explicit = _has_any_parm(node, ("f1", "f2", "f3"))
    if has_explicit:
        start = _eval_number(node, ("f1",), scene_start)
        end = _eval_number(node, ("f2",), scene_end)
        step = _eval_number(node, ("f3",), scene_step)
        return start, end, step or 1.0, "Render Node"

    return scene_start, scene_end, scene_step, "Houdini Timeline"


def resolution_for_node(node):
    width = int(_eval_number(node, ("res1", "resolutionx", "width"), 0))
    height = int(_eval_number(node, ("res2", "resolutiony", "height"), 0))
    return width, height


def _descendants(root, max_nodes=1000):
    if root is None:
        return []
    result = []
    pending = []
    try:
        pending.extend(list(root.children()))
    except Exception:
        return result
    while pending and len(result) < int(max_nodes):
        node = pending.pop(0)
        result.append(node)
        try:
            pending.extend(list(node.children()))
        except Exception:
            pass
    return result


def object_camera_paths():
    try:
        import hou
        root = hou.node("/obj")
    except Exception:
        root = None
    cameras = []
    for node in _descendants(root, max_nodes=2000):
        type_name = _node_type_name(node).lower()
        label = _node_type_label(node).lower()
        if type_name in ("cam", "camera") or "camera" in label:
            try:
                cameras.append(str(node.path()))
            except Exception:
                pass
    return tuple(_unique(cameras))


def _stage_for_node(node):
    candidates = [node]
    try:
        candidates.extend([item for item in node.inputs() if item is not None])
    except Exception:
        pass
    for candidate in candidates:
        try:
            stage_method = getattr(candidate, "stage", None)
            if callable(stage_method):
                stage = stage_method()
                if stage is not None:
                    return stage
        except Exception:
            pass
    return None


def _prim_valid(prim):
    if prim is None:
        return False
    try:
        return bool(prim.IsValid())
    except Exception:
        try:
            return bool(prim)
        except Exception:
            return False


def _prim_type_name(prim):
    try:
        return str(prim.GetTypeName() or "")
    except Exception:
        return ""


def _prim_path(prim):
    try:
        return str(prim.GetPath())
    except Exception:
        return ""


def _stage_prims(stage, max_prims=20000):
    if stage is None:
        return []
    try:
        traversal = stage.Traverse()
    except Exception:
        return []
    result = []
    try:
        for prim in traversal:
            result.append(prim)
            if len(result) >= int(max_prims):
                break
    except Exception:
        pass
    return result


def stage_camera_paths(stage):
    return tuple(_unique(
        _prim_path(prim)
        for prim in _stage_prims(stage)
        if _prim_type_name(prim).lower() == "camera"
    ))


def _attribute_value(prim, name):
    if not _prim_valid(prim):
        return None
    try:
        attribute = prim.GetAttribute(name)
        if attribute:
            return attribute.Get()
    except Exception:
        pass
    return None


def _relationship_targets(prim, name):
    if not _prim_valid(prim):
        return []
    try:
        relationship = prim.GetRelationship(name)
        if relationship:
            return [str(value) for value in relationship.GetTargets()]
    except Exception:
        pass
    return []


def _render_settings_prim(stage, node):
    settings_path = str(_eval_parm(node, _RENDER_SETTINGS_PARMS, "") or "").strip()
    if stage is not None and settings_path:
        try:
            prim = stage.GetPrimAtPath(settings_path)
            if _prim_valid(prim):
                return prim
        except Exception:
            pass
    for prim in _stage_prims(stage):
        if _prim_type_name(prim).lower() == "rendersettings":
            return prim
    return None


def _usd_render_details(node):
    stage = _stage_for_node(node)
    settings_prim = _render_settings_prim(stage, node)
    camera = ""
    output_path = ""
    width = 0
    height = 0

    camera_targets = _relationship_targets(settings_prim, "camera")
    if camera_targets:
        camera = camera_targets[0]

    resolution = _attribute_value(settings_prim, "resolution")
    if resolution is not None:
        try:
            width = int(resolution[0])
            height = int(resolution[1])
        except Exception:
            pass

    product_paths = _relationship_targets(settings_prim, "products")
    if not product_paths and stage is not None:
        product_paths = [
            _prim_path(prim)
            for prim in _stage_prims(stage)
            if _prim_type_name(prim).lower() == "rendervar"
            or _prim_type_name(prim).lower() == "renderproduct"
        ]

    for product_path in product_paths:
        try:
            product = stage.GetPrimAtPath(product_path)
        except Exception:
            product = None
        value = _attribute_value(product, "productName")
        if value not in (None, ""):
            output_path = str(value)
            break

    return {
        "camera": camera,
        "output_path": output_path,
        "width": width,
        "height": height,
        "cameras": stage_camera_paths(stage),
    }


def inspect_render_node(node, scene_range=None, evaluate_parameters=True):
    if node is None:
        return None

    execution_mode = execution_mode_for_node(node)
    renderer = renderer_for_node(node, evaluate_parameters=evaluate_parameters)
    usd_output_path = ""
    output_source = "render_node"

    if evaluate_parameters:
        start, end, step, source = frame_range_for_node(node, scene_range)
        width, height = resolution_for_node(node)
        camera = str(_eval_parm(node, _CAMERA_PARMS, "") or "")

        if execution_mode == "husk":
            usd_output_path = str(_eval_parm(node, _USD_OUTPUT_PARMS, "") or "")
            output_path = str(_eval_parm(node, _IMAGE_OUTPUT_PARMS, "") or "")
            usd_details = _usd_render_details(node)
            camera = camera or usd_details.get("camera", "")
            output_path = output_path or usd_details.get("output_path", "")
            width = width or int(usd_details.get("width") or 0)
            height = height or int(usd_details.get("height") or 0)
            cameras = usd_details.get("cameras") or ()
            if output_path:
                output_source = "usd_render_product"
        else:
            output_path = str(_eval_parm(node, _GENERIC_OUTPUT_PARMS, "") or "")
            cameras = object_camera_paths()
    else:
        start, end, step = scene_range or _scene_frame_range()
        source = "Houdini Timeline"
        width, height = 0, 0
        camera = ""
        output_path = ""
        cameras = ()

    cameras = tuple(_unique(([camera] if camera else []) + list(cameras or [])))
    renderers = available_renderers_for_node(node, renderer) if evaluate_parameters else ((renderer,) if renderer else ())

    try:
        path = str(node.path())
    except Exception:
        path = ""
    try:
        name = str(node.name())
    except Exception:
        name = path.rsplit("/", 1)[-1] if path else ""

    return RenderNodeInfo(
        path=path,
        name=name,
        type_name=_node_type_name(node),
        type_label=_node_type_label(node),
        category=_category_name(node),
        renderer=renderer,
        execution_mode=execution_mode,
        frame_start=float(start),
        frame_end=float(end),
        frame_step=float(step),
        frame_source=source,
        camera=camera,
        output_path=output_path,
        resolution_width=width,
        resolution_height=height,
        is_bypassed=_bool_method(node, "isBypassed"),
        is_locked=_bool_method(node, "isLockedHDA"),
        is_renderable=is_supported_render_node(node),
        available_cameras=cameras,
        available_renderers=renderers,
        usd_output_path=usd_output_path,
        output_source=output_source,
        details_loaded=bool(evaluate_parameters),
    )


def discover_render_nodes():
    """Safely discover executable nodes under /out and /stage."""
    import hou

    found = []
    seen = set()
    scene_range = _scene_frame_range()

    for root_path in ("/out", "/stage"):
        try:
            root = hou.node(root_path)
        except Exception:
            root = None

        for node in _descendants(root):
            if not is_supported_render_node(node):
                continue
            info = inspect_render_node(
                node,
                scene_range=scene_range,
                evaluate_parameters=False,
            )
            if info is None or not info.path or info.path in seen:
                continue
            seen.add(info.path)
            found.append(info)

    found.sort(key=lambda item: (item.path.lower(), item.type_name.lower()))
    return found


def selected_render_node():
    import hou

    try:
        selected = list(hou.selectedNodes())
    except Exception:
        selected = []

    scene_range = _scene_frame_range()
    for node in reversed(selected):
        if is_supported_render_node(node):
            return inspect_render_node(node, scene_range=scene_range)
    return None


def node_info_from_path(path):
    import hou
    try:
        node = hou.node(str(path or ""))
    except Exception:
        node = None
    if node is None or not is_supported_render_node(node):
        return None
    return inspect_render_node(node)
