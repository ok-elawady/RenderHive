from __future__ import absolute_import

import re


def _integer(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def _list(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def normalize_pool(value):
    value = value if isinstance(value, dict) else {}
    workers = value.get("workers") if isinstance(value.get("workers"), list) else []
    return {
        "id": str(value.get("id") or ""),
        "name": str(value.get("name") or "Unnamed Pool"),
        "description": str(value.get("description") or ""),
        "workers": workers,
        "worker_count": _integer(value.get("worker_count"), len(workers)),
        "created_at": str(value.get("created_at") or ""),
        "updated_at": str(value.get("updated_at") or ""),
    }


def normalize_worker(value):
    value = value if isinstance(value, dict) else {}
    pools = [normalize_pool(item) for item in _list(value.get("pools")) if isinstance(item, dict)]
    system_info = value.get("system_info") if isinstance(value.get("system_info"), dict) else {}
    tags = [str(item) for item in _list(value.get("tags")) if str(item).strip()]
    gpu_models = value.get("gpu_models") or system_info.get("gpu_models") or system_info.get("gpus") or []
    if isinstance(gpu_models, str):
        gpu_models = [gpu_models]
    capabilities = system_info.get("capabilities") if isinstance(system_info.get("capabilities"), dict) else {}
    return {
        "id": str(value.get("id") or ""),
        "hostname": str(value.get("hostname") or value.get("name") or "Unnamed Worker"),
        "ip_address": str(value.get("ip_address") or system_info.get("ip_address") or ""),
        "status": str(value.get("status") or "UNKNOWN").upper(),
        "pools": pools,
        "tags": tags,
        "cores": _integer(value.get("cores") or system_info.get("cpu_cores"), 0),
        "memory_mb": _integer(value.get("memory_mb") or system_info.get("memory_mb"), 0),
        "gpu_models": [str(item) for item in gpu_models if str(item).strip()],
        "system_info": system_info,
        "capabilities": capabilities,
        "last_ping": str(value.get("last_ping") or ""),
        "created_at": str(value.get("created_at") or ""),
    }


def worker_is_online(worker):
    return str((worker or {}).get("status") or "").upper() in (
        "ONLINE", "IDLE", "AVAILABLE", "RENDERING", "BUSY", "WORKING",
    )


def worker_memory_label(worker):
    memory_mb = _integer((worker or {}).get("memory_mb"), 0)
    if memory_mb <= 0:
        return "—"
    memory_gb = float(memory_mb) / 1024.0
    return "{} GB".format(int(round(memory_gb))) if abs(memory_gb - round(memory_gb)) < 0.05 else "{:.1f} GB".format(memory_gb)


def worker_gpu_label(worker):
    values = [str(value).strip() for value in ((worker or {}).get("gpu_models") or [])]
    values = [value for value in values if value]
    return ", ".join(values) if values else "—"


def _version_key(value, dcc):
    text = str(value or "")
    numbers = re.findall(r"\d+", text)
    if not numbers:
        return ""
    if str(dcc).lower() == "maya":
        return numbers[0]
    return ".".join(numbers[:2])


def worker_houdini_versions(worker):
    caps = (worker or {}).get("capabilities") or {}
    data = caps.get("houdini") if isinstance(caps, dict) else {}
    versions = data.get("versions") if isinstance(data, dict) else []
    if not versions:
        info = (worker or {}).get("system_info") or {}
        dcc = info.get("dcc_applications") or info.get("dcc") or {}
        houdini = dcc.get("houdini") if isinstance(dcc, dict) else {}
        versions = houdini.get("versions") if isinstance(houdini, dict) else []
    if not versions:
        versions = [tag.split(":", 1)[1] for tag in (worker or {}).get("tags", []) if str(tag).lower().startswith("houdini:") and any(ch.isdigit() for ch in str(tag))]
    return [str(item) for item in versions or []]


def worker_execution_modes(worker):
    caps = (worker or {}).get("capabilities") or {}
    data = caps.get("houdini") if isinstance(caps, dict) else {}
    modes = data.get("execution_modes") if isinstance(data, dict) else []
    if not modes:
        tags = [str(tag).lower() for tag in (worker or {}).get("tags", [])]
        modes = [mode for mode in ("hython", "husk") if "houdini:{}".format(mode) in tags]
    return [str(item).lower() for item in modes or []]


def worker_supports_houdini(worker, version="", execution_mode="", renderer=""):
    if not worker_is_online(worker):
        return False
    requested = _version_key(version, "houdini")
    versions = worker_houdini_versions(worker)
    if requested and versions and requested not in [_version_key(item, "houdini") for item in versions]:
        return False
    mode = str(execution_mode or "").lower()
    modes = worker_execution_modes(worker)
    if mode and modes and mode not in modes:
        return False
    renderer_key = str(renderer or "").lower().replace(" ", "-")
    if renderer_key:
        tags = [str(tag).lower() for tag in (worker or {}).get("tags", [])]
        renderer_tags = [tag for tag in tags if tag.startswith("renderer:") or tag.startswith("houdini-renderer:")]
        if renderer_tags and not any(renderer_key in tag for tag in renderer_tags):
            return False
    return True


def worker_gpu_count(worker):
    """Best-effort GPU count from normalized worker telemetry."""
    worker = worker or {}
    models = [str(value).strip() for value in (worker.get("gpu_models") or []) if str(value).strip()]
    if models:
        return len(models)
    info = worker.get("system_info") if isinstance(worker.get("system_info"), dict) else {}
    for key in ("gpu_count", "gpus_count", "num_gpus"):
        value = _integer(info.get(key), 0)
        if value > 0:
            return value
    gpus = info.get("gpus")
    if isinstance(gpus, (list, tuple)):
        return len(gpus)
    return 0


def worker_meets_requirements(worker, min_cores=0, min_memory_mb=0, min_gpus=0):
    """Return True when worker hardware meets backend layer requirements."""
    worker = worker or {}
    required_cores = max(0, _integer(min_cores, 0))
    required_memory = max(0, _integer(min_memory_mb, 0))
    required_gpus = max(0, _integer(min_gpus, 0))

    cores = max(0, _integer(worker.get("cores"), 0))
    memory_mb = max(0, _integer(worker.get("memory_mb"), 0))
    gpus = worker_gpu_count(worker)

    if required_cores and cores < required_cores:
        return False
    if required_memory and memory_mb < required_memory:
        return False
    if required_gpus and gpus < required_gpus:
        return False
    return True
