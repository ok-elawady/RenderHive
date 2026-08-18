from __future__ import absolute_import


def worker_identifier(worker):
    if not isinstance(worker, dict):
        return str(worker or "").strip()

    return str(
        worker.get("id")
        or worker.get("worker_id")
        or worker.get("hostname")
        or worker.get("name")
        or ""
    ).strip()

def worker_display_name(worker):
    if not isinstance(worker, dict):
        return str(worker or "").strip()

    return str(
        worker.get("hostname")
        or worker.get("machine_name")
        or worker.get("label")
        or worker.get("display_name")
        or worker.get("name")
        or worker_identifier(worker)
        or "Unnamed Worker"
    ).strip()

def worker_status(worker):
    if not isinstance(worker, dict):
        return ""

    return str(
        worker.get("status")
        or worker.get("state")
        or ""
    ).strip().upper()

def worker_is_online(worker):
    status = worker_status(worker)

    if status in (
        "OFFLINE",
        "DISCONNECTED",
        "DISABLED",
    ):
        return False

    if isinstance(worker, dict):
        available = worker.get("available")
        if available is False:
            return False

    return status in (
        "",
        "ONLINE",
        "IDLE",
        "AVAILABLE",
        "RENDERING",
        "BUSY",
        "WORKING",
    )

def _safe_number(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None

def worker_memory_gb(worker):
    if not isinstance(worker, dict):
        return None

    direct_gb = _safe_number(
        worker.get("ram_gb")
        or worker.get("memory_gb")
    )
    if direct_gb is not None:
        return direct_gb

    memory_mb = _safe_number(
        worker.get("memory_mb")
        or worker.get("ram_mb")
    )
    if memory_mb is not None:
        return memory_mb / 1024.0

    system_info = worker.get("system_info")
    if isinstance(system_info, dict):
        direct_gb = _safe_number(
            system_info.get("ram_gb")
            or system_info.get("memory_gb")
        )
        if direct_gb is not None:
            return direct_gb

        memory_mb = _safe_number(
            system_info.get("memory_mb")
            or system_info.get("ram_mb")
            or system_info.get("total_memory_mb")
        )
        if memory_mb is not None:
            return memory_mb / 1024.0

    return None


def worker_gpu_text(worker):
    if not isinstance(worker, dict):
        return "—"

    values = (
        worker.get("gpu_models")
        or worker.get("gpus")
        or worker.get("gpu_model")
        or []
    )

    if isinstance(values, str):
        values = [values]

    if isinstance(values, (list, tuple)):
        labels = []
        for value in values:
            if isinstance(value, dict):
                label = str(
                    value.get("name")
                    or value.get("model")
                    or ""
                ).strip()
            else:
                label = str(value or "").strip()

            if label and label not in labels:
                labels.append(label)

        if labels:
            return ", ".join(labels)

    system_info = worker.get("system_info")
    if isinstance(system_info, dict):
        value = (
            system_info.get("gpu_models")
            or system_info.get("gpus")
            or system_info.get("gpu")
        )
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (list, tuple)):
            labels = [str(item).strip() for item in value if str(item).strip()]
            if labels:
                return ", ".join(labels)

    return "—"

def format_gb(value):
    number = _safe_number(value)
    if number is None:
        return "—"

    if abs(number - round(number)) < 0.05:
        return "{} GB".format(int(round(number)))

    return "{:.1f} GB".format(number)

def pool_identifier(pool):
    if not isinstance(pool, dict):
        return str(pool or "").strip()
    return str(pool.get("id") or pool.get("name") or "").strip()

def pool_display_name(pool):
    if not isinstance(pool, dict):
        return str(pool or "").strip()
    return str(pool.get("name") or pool_identifier(pool) or "Unnamed Pool").strip()


def worker_core_count(worker):
    if not isinstance(worker, dict):
        return None

    value = _safe_number(worker.get("cores") or worker.get("cpu_cores"))
    if value is not None:
        return max(0, int(value))

    system_info = worker.get("system_info")
    if isinstance(system_info, dict):
        value = _safe_number(
            system_info.get("cores")
            or system_info.get("cpu_cores")
            or system_info.get("logical_cores")
        )
        if value is not None:
            return max(0, int(value))

    return None


def worker_gpu_count(worker):
    if not isinstance(worker, dict):
        return None

    values = worker.get("gpu_models") or worker.get("gpus")
    if isinstance(values, (list, tuple)):
        return len([item for item in values if item not in (None, "")])
    if isinstance(values, str) and values.strip():
        return 1

    system_info = worker.get("system_info")
    if isinstance(system_info, dict):
        explicit = _safe_number(
            system_info.get("gpu_count")
            or system_info.get("gpus_count")
        )
        if explicit is not None:
            return max(0, int(explicit))

        values = system_info.get("gpu_models") or system_info.get("gpus")
        if isinstance(values, (list, tuple)):
            return len([item for item in values if item not in (None, "")])
        if isinstance(values, str) and values.strip():
            return 1

        gpu = system_info.get("gpu")
        if isinstance(gpu, str) and gpu.strip() and gpu.strip().lower() not in (
            "none", "not detected", "n/a", "unknown"
        ):
            return 1

    return 0


def worker_meets_requirements(worker, minimum_cores=0, minimum_ram_gb=0, minimum_gpus=0):
    """Match the backend's numeric worker resource gates for UI previews."""
    try:
        minimum_cores = max(0, int(minimum_cores or 0))
    except (TypeError, ValueError):
        minimum_cores = 0
    try:
        minimum_ram_gb = max(0, float(minimum_ram_gb or 0))
    except (TypeError, ValueError):
        minimum_ram_gb = 0.0
    try:
        minimum_gpus = max(0, int(minimum_gpus or 0))
    except (TypeError, ValueError):
        minimum_gpus = 0

    if minimum_cores:
        cores = worker_core_count(worker)
        if cores is None or cores < minimum_cores:
            return False

    if minimum_ram_gb:
        ram_gb = worker_memory_gb(worker)
        if ram_gb is None or ram_gb < minimum_ram_gb:
            return False

    if minimum_gpus:
        gpu_count = worker_gpu_count(worker)
        if gpu_count is None or gpu_count < minimum_gpus:
            return False

    return True
