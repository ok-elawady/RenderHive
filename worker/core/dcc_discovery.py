"""Discover installed Maya and Houdini versions on Windows.

The worker never imports Maya or Houdini Python modules. It only discovers and
launches the executables installed on the machine, so one worker build can
support every detected DCC version.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


_VERSION_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


@dataclass(frozen=True)
class DCCInstallation:
    dcc: str
    version: str
    root: str
    executables: Dict[str, str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _version_tuple(value: str) -> Tuple[int, int, int]:
    match = _VERSION_RE.search(str(value or ""))
    if not match:
        return (0, 0, 0)
    parts = [int(item or 0) for item in match.groups()]
    return tuple(parts)  # type: ignore[return-value]


def _clean_path(path: str) -> str:
    return os.path.normpath(os.path.abspath(os.path.expandvars(os.path.expanduser(path))))


def _existing(path: str) -> str:
    cleaned = _clean_path(path)
    return cleaned if os.path.isfile(cleaned) else ""


def _unique_paths(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        if not value:
            continue
        cleaned = _clean_path(value)
        key = os.path.normcase(cleaned)
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _installation_score(item: DCCInstallation) -> int:
    """Rank duplicate installation records without launching the DCC.

    Registry, Program Files globbing, and explicit roots can all point to the
    same installed version. Prefer the record that exposes more executable
    entry points. On a tie, the later record wins so an explicit ``extra_roots``
    path can override an automatically discovered path.
    """

    return sum(1 for value in item.executables.values() if value)


def _dedupe_installations(
    installations: Sequence[DCCInstallation],
    preferred_roots: Optional[Sequence[str]] = None,
) -> List[DCCInstallation]:
    """Collapse duplicate records for the same DCC version.

    Maya is identified by its release year and Houdini by its full version/build
    string. Unknown versions remain distinct by install root so no valid custom
    installation is accidentally discarded.

    ``preferred_roots`` are caller-supplied/manual locations. They always win
    over registry or Program Files discovery, even when the automatic record
    exposes more executables. When several preferred roots describe the same
    version, the last preferred root wins. This makes manual overrides
    deterministic and also prevents machine-local installations from leaking
    into isolated discovery tests.
    """

    preferred = {
        os.path.normcase(_clean_path(value))
        for value in (preferred_roots or [])
        if value
    }
    selected: Dict[Tuple[object, ...], DCCInstallation] = {}
    order: List[Tuple[object, ...]] = []

    for item in installations:
        parsed_version = _version_tuple(item.version)
        if parsed_version == (0, 0, 0):
            key: Tuple[object, ...] = (
                item.dcc.lower(),
                "root",
                os.path.normcase(_clean_path(item.root)),
            )
        else:
            dcc_name = item.dcc.lower()
            version_key: object
            if dcc_name == "maya":
                # Maya patch releases share the same executable installation
                # year for worker selection, for example 2023 and 2023.2.
                version_key = parsed_version[0]
            else:
                # Keep separate Houdini production builds installed side by
                # side, such as 20.5.278 and 20.5.410.
                version_key = parsed_version
            key = (dcc_name, "version", version_key)

        existing = selected.get(key)
        if existing is None:
            selected[key] = item
            order.append(key)
            continue

        item_is_preferred = os.path.normcase(_clean_path(item.root)) in preferred
        existing_is_preferred = os.path.normcase(_clean_path(existing.root)) in preferred

        if item_is_preferred:
            # Manual roots are appended after automatic discovery. Replacing
            # here also means the last manual root is the intentional winner.
            selected[key] = item
            continue
        if existing_is_preferred:
            continue

        # For automatic duplicates, keep the most complete installation record.
        # Replace on equal score to preserve the previous deterministic order.
        if _installation_score(item) >= _installation_score(existing):
            selected[key] = item

    return [selected[key] for key in order]


def _registry_install_roots(dcc: str) -> List[str]:
    if os.name != "nt":
        return []

    try:
        import winreg  # type: ignore
    except Exception:
        return []

    roots: List[str] = []
    registry_views = [0]
    for flag_name in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
        flag = getattr(winreg, flag_name, 0)
        if flag not in registry_views:
            registry_views.append(flag)

    if dcc == "maya":
        base_keys = [
            r"SOFTWARE\Autodesk\Maya",
            r"SOFTWARE\WOW6432Node\Autodesk\Maya",
        ]
        value_names = ("MAYA_INSTALL_LOCATION", "InstallPath", "INSTALLDIR")
    else:
        base_keys = [
            r"SOFTWARE\Side Effects Software",
            r"SOFTWARE\WOW6432Node\Side Effects Software",
        ]
        value_names = ("InstallPath", "INSTALLDIR")

    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for base_key in base_keys:
            for view in registry_views:
                try:
                    handle = winreg.OpenKey(hive, base_key, 0, winreg.KEY_READ | view)
                except OSError:
                    continue
                try:
                    subkey_count = winreg.QueryInfoKey(handle)[0]
                    for index in range(subkey_count):
                        try:
                            subkey_name = winreg.EnumKey(handle, index)
                            subkey = winreg.OpenKey(handle, subkey_name)
                        except OSError:
                            continue
                        try:
                            for value_name in value_names:
                                try:
                                    value = winreg.QueryValueEx(subkey, value_name)[0]
                                except OSError:
                                    continue
                                if value:
                                    roots.append(str(value))
                        finally:
                            winreg.CloseKey(subkey)
                finally:
                    winreg.CloseKey(handle)
    return roots


def discover_maya_installations(extra_roots: Optional[Sequence[str]] = None) -> List[DCCInstallation]:
    roots: List[str] = []
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    roots.extend(glob.glob(os.path.join(program_files, "Autodesk", "Maya*")))
    roots.extend(glob.glob(os.path.join(program_files_x86, "Autodesk", "Maya*")))
    roots.extend(_registry_install_roots("maya"))
    roots.extend(extra_roots or [])

    installations: List[DCCInstallation] = []
    for root in _unique_paths(roots):
        path = Path(root)
        version_match = re.search(r"Maya\s*(\d{4}(?:\.\d+)?)", path.name, re.IGNORECASE)
        version = version_match.group(1) if version_match else ""

        render_exe = _existing(str(path / "bin" / "Render.exe"))
        mayapy_exe = _existing(str(path / "bin" / "mayapy.exe"))
        maya_exe = _existing(str(path / "bin" / "maya.exe"))
        if not any((render_exe, mayapy_exe, maya_exe)):
            continue

        if not version:
            version = path.name.replace("Maya", "").strip() or "unknown"

        installations.append(
            DCCInstallation(
                dcc="maya",
                version=version,
                root=str(path),
                executables={
                    "render": render_exe,
                    "mayapy": mayapy_exe,
                    "maya": maya_exe,
                },
            )
        )

    installations = _dedupe_installations(installations, extra_roots)
    return sorted(installations, key=lambda item: _version_tuple(item.version), reverse=True)


def discover_houdini_installations(extra_roots: Optional[Sequence[str]] = None) -> List[DCCInstallation]:
    roots: List[str] = []
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    roots.extend(glob.glob(os.path.join(program_files, "Side Effects Software", "Houdini *")))
    roots.extend(glob.glob(os.path.join(program_files, "Side Effects Software", "Houdini*")))
    roots.extend(glob.glob(os.path.join(program_files_x86, "Side Effects Software", "Houdini *")))
    roots.extend(_registry_install_roots("houdini"))
    roots.extend(extra_roots or [])

    installations: List[DCCInstallation] = []
    for root in _unique_paths(roots):
        path = Path(root)
        version_match = re.search(r"Houdini\s*(\d+(?:\.\d+){1,2})", path.name, re.IGNORECASE)
        version = version_match.group(1) if version_match else ""

        hython_exe = _existing(str(path / "bin" / "hython.exe"))
        husk_exe = _existing(str(path / "bin" / "husk.exe"))
        hbatch_exe = _existing(str(path / "bin" / "hbatch.exe"))
        houdini_exe = _existing(str(path / "bin" / "houdini.exe"))
        if not any((hython_exe, husk_exe, hbatch_exe, houdini_exe)):
            continue

        if not version:
            version = path.name.replace("Houdini", "").strip() or "unknown"

        installations.append(
            DCCInstallation(
                dcc="houdini",
                version=version,
                root=str(path),
                executables={
                    "hython": hython_exe,
                    "husk": husk_exe,
                    "hbatch": hbatch_exe,
                    "houdini": houdini_exe,
                },
            )
        )

    installations = _dedupe_installations(installations, extra_roots)
    return sorted(installations, key=lambda item: _version_tuple(item.version), reverse=True)


def discover_all(extra_maya_roots: Optional[Sequence[str]] = None, extra_houdini_roots: Optional[Sequence[str]] = None) -> Dict[str, List[DCCInstallation]]:
    return {
        "maya": discover_maya_installations(extra_maya_roots),
        "houdini": discover_houdini_installations(extra_houdini_roots),
    }


def select_installation(installations: Sequence[DCCInstallation], requested_version: str = "") -> Optional[DCCInstallation]:
    if not installations:
        return None

    requested = _version_tuple(requested_version)
    if requested == (0, 0, 0):
        return sorted(installations, key=lambda item: _version_tuple(item.version), reverse=True)[0]

    exact = [item for item in installations if _version_tuple(item.version) == requested]
    if exact:
        return exact[0]

    # Maya versions are primarily selected by year. Houdini versions are
    # selected by major.minor, while allowing a different production build.
    dcc = installations[0].dcc
    if dcc == "maya":
        compatible = [item for item in installations if _version_tuple(item.version)[0] == requested[0]]
    else:
        compatible = [
            item
            for item in installations
            if _version_tuple(item.version)[:2] == requested[:2]
        ]

    if compatible:
        return sorted(compatible, key=lambda item: _version_tuple(item.version), reverse=True)[0]
    return None


def build_capabilities(discovered: Dict[str, Sequence[DCCInstallation]]) -> Dict[str, object]:
    maya_items = list(discovered.get("maya") or [])
    houdini_items = list(discovered.get("houdini") or [])

    capabilities = {
        "maya": {
            "available": bool(maya_items),
            "versions": [item.version for item in maya_items],
            "render_executables": [item.executables.get("render", "") for item in maya_items if item.executables.get("render")],
        },
        "houdini": {
            "available": bool(houdini_items),
            "versions": [item.version for item in houdini_items],
            "execution_modes": sorted(
                {
                    mode
                    for item in houdini_items
                    for mode in ("hython" if item.executables.get("hython") else "", "husk" if item.executables.get("husk") else "")
                    if mode
                }
            ),
        },
    }
    return capabilities


def build_capability_tags(discovered: Dict[str, Sequence[DCCInstallation]]) -> List[str]:
    tags: List[str] = []
    for item in discovered.get("maya") or []:
        tags.extend(["dcc:maya", "maya:{}".format(item.version)])
    for item in discovered.get("houdini") or []:
        tags.extend(["dcc:houdini", "houdini:{}".format(item.version)])
        if item.executables.get("hython"):
            tags.append("houdini:hython")
        if item.executables.get("husk"):
            tags.append("houdini:husk")

    result: List[str] = []
    for tag in tags:
        if tag and tag not in result:
            result.append(tag[:64])
    return result
