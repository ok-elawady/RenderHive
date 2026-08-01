from __future__ import absolute_import


def _integer(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def normalize_pool(value):
    value = value if isinstance(value, dict) else {}
    return {
        "id": str(value.get("id") or ""),
        "name": str(value.get("name") or "Unnamed Pool"),
        "description": str(value.get("description") or ""),
        "created_at": str(value.get("created_at") or ""),
        "updated_at": str(value.get("updated_at") or ""),
    }


def normalize_worker(value):
    value = value if isinstance(value, dict) else {}
    pools = [
        normalize_pool(item)
        for item in (value.get("pools") or [])
        if isinstance(item, dict)
    ]
    system_info = value.get("system_info")
    if not isinstance(system_info, dict):
        system_info = {}

    return {
        "id": str(value.get("id") or ""),
        "hostname": str(value.get("hostname") or value.get("name") or "Unnamed Worker"),
        "ip_address": str(value.get("ip_address") or ""),
        "status": str(value.get("status") or "UNKNOWN").upper(),
        "pools": pools,
        "tags": list(value.get("tags") or []),
        "cores": _integer(value.get("cores"), 0),
        "memory_mb": _integer(value.get("memory_mb"), 0),
        "gpu_models": list(value.get("gpu_models") or []),
        "system_info": system_info,
        "last_ping": str(value.get("last_ping") or ""),
        "created_at": str(value.get("created_at") or ""),
    }


def worker_is_online(worker):
    return str((worker or {}).get("status") or "").upper() in (
        "ONLINE",
        "IDLE",
        "AVAILABLE",
        "RENDERING",
        "BUSY",
        "WORKING",
    )


def worker_memory_label(worker):
    memory_mb = _integer((worker or {}).get("memory_mb"), 0)
    if memory_mb <= 0:
        return "—"
    memory_gb = float(memory_mb) / 1024.0
    if abs(memory_gb - round(memory_gb)) < 0.05:
        return "{} GB".format(int(round(memory_gb)))
    return "{:.1f} GB".format(memory_gb)


def worker_gpu_label(worker):
    values = [str(value).strip() for value in ((worker or {}).get("gpu_models") or [])]
    values = [value for value in values if value]
    return ", ".join(values) if values else "—"
