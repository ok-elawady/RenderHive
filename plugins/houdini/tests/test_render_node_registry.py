from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs" / "renderhive_houdini"
MODULE_PATH = ROOT / "adapters" / "render_node_registry.py"
spec = importlib.util.spec_from_file_location("render_node_registry_under_test", str(MODULE_PATH))
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)


class FakeParm:
    def __init__(self, value):
        self.value = value

    def eval(self):
        return self.value


class FakeCategory:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class FakeType:
    def __init__(self, name, label, category):
        self._name = name
        self._label = label
        self._category = FakeCategory(category)

    def name(self):
        return self._name

    def description(self):
        return self._label

    def category(self):
        return self._category


class FakeNode:
    def __init__(self, path, type_name, label, category, parms=None, bypassed=False):
        self._path = path
        self._type = FakeType(type_name, label, category)
        self._parms = dict(parms or {})
        self._bypassed = bypassed

    def path(self):
        return self._path

    def name(self):
        return self._path.rsplit("/", 1)[-1]

    def type(self):
        return self._type

    def parm(self, name):
        if name not in self._parms:
            return None
        return FakeParm(self._parms[name])

    def isBypassed(self):
        return self._bypassed

    def isLockedHDA(self):
        return False


def test_generic_driver_node_is_supported_and_inspected():
    node = FakeNode(
        "/out/arnold1",
        "arnold",
        "Arnold ROP",
        "Driver",
        {
            "trange": 1,
            "f1": 1,
            "f2": 48,
            "f3": 2,
            "ar_picture": "$HIP/render/beauty.$F4.exr",
            "camera": "/obj/cam1",
            "res1": 1920,
            "res2": 1080,
        },
    )
    assert registry.is_supported_render_node(node)
    info = registry.inspect_render_node(node, scene_range=(1, 240, 1))
    assert info.renderer == "Arnold"
    assert info.execution_mode == "hython"
    assert info.frame_end == 48
    assert info.output_path.endswith("beauty.$F4.exr")
    assert info.resolution_width == 1920


def test_render_settings_lop_is_not_executable():
    node = FakeNode(
        "/stage/karmarendersettings1",
        "karmarendersettings",
        "Karma Render Settings",
        "Lop",
        {"rendercamera": "/cameras/cam1"},
    )
    assert not registry.is_supported_render_node(node)


def test_usd_render_rop_uses_husk():
    node = FakeNode(
        "/stage/usdrender_rop1",
        "usdrender_rop",
        "USD Render ROP",
        "Lop",
        {
            "execute": 1,
            "lopoutput": "$HIP/usd/render.usd",
            "renderer": "KarmaXPU",
        },
    )
    assert registry.is_supported_render_node(node)
    info = registry.inspect_render_node(node, scene_range=(1, 24, 1))
    assert info.execution_mode == "husk"
    assert info.renderer == "Karma XPU"
