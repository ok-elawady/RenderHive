from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs"
sys.path.insert(0, str(ROOT))

from renderhive_houdini.core.state_store import StateStore


def test_state_roundtrip_and_isolation(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    store.save("P:/a.hip", {"job": {"priority": 60}})
    store.save("P:/b.hip", {"job": {"priority": 20}})
    assert store.load("P:/a.hip")["job"]["priority"] == 60
    assert store.load("P:/b.hip")["job"]["priority"] == 20
    assert store.count() == 2
    assert store.integrity_ok()


def test_state_delete(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    store.save("P:/a.hip", {"x": 1})
    store.delete("P:/a.hip")
    assert store.load("P:/a.hip") == {}
