"""Collect external files referenced by the current Houdini scene without cooking nodes."""

from __future__ import absolute_import

import glob
import os
import re

_SEQUENCE_TOKEN = re.compile(r"(\$F\d*|<UDIM>|%0\d+d|#+)", re.IGNORECASE)


def classify_path(path):
    extension = os.path.splitext(str(path or ""))[1].lower()
    if extension in (".exr", ".tx", ".rat", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".hdr", ".pic"):
        return "Texture"
    if extension in (".abc", ".bgeo", ".bgeo.sc", ".obj", ".fbx", ".geo"):
        return "Geometry"
    if extension in (".vdb",):
        return "VDB"
    if extension in (".usd", ".usda", ".usdc", ".usdz"):
        return "USD"
    if extension in (".hda", ".otl"):
        return "HDA"
    if extension in (".sim", ".dop", ".cache"):
        return "Cache"
    if extension in (".hip", ".hiplc", ".hipnc"):
        return "HIP Reference"
    return "File"


def _token_glob(path):
    text = str(path or "")
    text = re.sub(r"\$F\d*", "*", text, flags=re.IGNORECASE)
    text = re.sub(r"<UDIM>", "*", text, flags=re.IGNORECASE)
    text = re.sub(r"%0\d+d", "*", text)
    text = re.sub(r"#+", "*", text)
    return text


def _exists(path):
    if not path:
        return False
    if os.path.exists(path):
        return True
    if _SEQUENCE_TOKEN.search(path):
        try:
            return bool(glob.glob(_token_glob(path)))
        except Exception:
            return False
    return False


def _expand(hou, value):
    try:
        return os.path.normpath(str(hou.expandString(str(value or "")) or ""))
    except Exception:
        return os.path.normpath(str(value or "")) if value else ""


def collect_dependencies():
    """Return normalized dependency dictionaries from hou.fileReferences()."""
    import hou

    results = []
    seen = set()
    try:
        references = hou.fileReferences() or []
    except Exception:
        references = []

    for parm, raw_path in references:
        raw = str(raw_path or "").strip()
        if not raw:
            continue
        resolved = _expand(hou, raw)
        key = os.path.normcase(resolved or raw)
        if key in seen:
            continue
        seen.add(key)
        node_path = ""
        parm_name = ""
        try:
            parm_name = str(parm.name())
            node_path = str(parm.node().path())
        except Exception:
            pass
        results.append({
            "raw_path": raw,
            "resolved_path": resolved,
            "exists": _exists(resolved),
            "type": classify_path(resolved or raw),
            "node": node_path,
            "parameter": parm_name,
            "tokenized": bool(_SEQUENCE_TOKEN.search(raw)),
        })
    return results


def dependency_summary(dependencies):
    values = list(dependencies or [])
    return {
        "total": len(values),
        "missing": len([item for item in values if not item.get("exists")]),
        "types": sorted(set(str(item.get("type") or "File") for item in values)),
    }
