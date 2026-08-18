from __future__ import absolute_import

import datetime

from ..qt_compat import QtWidgets
from ..qt_theme import COLORS
from ..runtime_registry import WIDGETS as _WIDGETS
from ..common_widgets import WorkerStatusChip
from ..targeting_widgets import PoolMultiSelect, WorkerSyncThread
from ..worker_data import (
    pool_display_name,
    pool_identifier,
    worker_identifier,
    worker_is_online,
    worker_meets_requirements,
)


def _get_list(name, default=None):
    widget = _WIDGETS.get(name)
    if hasattr(widget, "selected_values"):
        try:
            return list(widget.selected_values() or [])
        except Exception:
            pass
    if hasattr(widget, "text"):
        try:
            value = widget.text()
            result = []
            for item in str(value or "").replace(";", ",").split(","):
                clean = item.strip()
                if clean and clean not in result:
                    result.append(clean)
            return result
        except Exception:
            pass
    return list(default or [])


def _set_list(name, values):
    widget = _WIDGETS.get(name)
    if hasattr(widget, "set_selected_values"):
        widget.set_selected_values(values or [])
        return
    if hasattr(widget, "setText"):
        widget.setText(", ".join(values or []))


class TargetingControllerMixin(object):
    def load_worker_pools(self):
        data = self.state_store.load_app_state(
            "worker_pools_v13",
            default={},
        )

        if not isinstance(data, dict):
            data = {}

        pools = {}
        for name, values in (data or {}).items():
            clean_name = str(name).strip()
            if not clean_name:
                continue

            clean_values = []
            for value in values or []:
                value = str(value).strip()
                if value and value not in clean_values:
                    clean_values.append(value)

            # Keep empty pool names too. Backend pools can exist before any
            # Worker has been assigned to them.
            pools[clean_name] = clean_values

        return pools

    def save_worker_pools(self):
        # SQLite keeps an offline cache. The backend remains authoritative.
        self.state_store.save_app_state("worker_pools_v13", self.worker_pools)

    @staticmethod
    def normalize_pools(payload):
        if isinstance(payload, dict):
            for key in ("pools", "items", "data", "results"):
                candidate = payload.get(key)
                if isinstance(candidate, (list, tuple)):
                    payload = candidate
                    break
            else:
                payload = []

        if not isinstance(payload, (list, tuple)):
            payload = []

        pools = []
        seen = set()
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            pool_id = str(entry.get("id") or "").strip()
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            key = pool_id or name.lower()
            if key in seen:
                continue
            seen.add(key)
            pools.append({
                "id": pool_id,
                "name": name,
                "description": str(entry.get("description") or ""),
                "created_at": entry.get("created_at"),
                "updated_at": entry.get("updated_at"),
            })

        pools.sort(key=lambda item: item["name"].lower())
        return pools


    def pool_assignment_strategy(self):
        widget=_WIDGETS.get("rh_pool_strategy")
        if hasattr(widget,"currentText"):
            try: return widget.currentText()
            except Exception: pass
        return "All Pools"

    def pool_assignment_strategy_key(self):
        return {"Selected Pools Only":"selected","All Except Selected":"all_except"}.get(
            self.pool_assignment_strategy(),"all"
        )

    def pool_record_by_id(self,pool_id):
        pool_id=str(pool_id or "").strip()
        for pool in self.api_pools:
            if pool_identifier(pool)==pool_id: return pool
        return None

    def pool_names_from_ids(self,pool_ids):
        result=[]
        for pool_id in pool_ids or []:
            record=self.pool_record_by_id(pool_id)
            name=pool_display_name(record) if record else str(pool_id)
            if name and name not in result: result.append(name)
        return result

    def selected_pool_ids(self):
        return _get_list("rh_selected_pools",[])

    def excluded_pool_ids(self):
        return _get_list("rh_excluded_pools",[])

    def effective_pool_records(self):
        pools=list(self.api_pools)
        strategy=self.pool_assignment_strategy_key()
        selected=set(self.selected_pool_ids())
        excluded=set(self.excluded_pool_ids())
        if strategy=="selected":
            return [p for p in pools if pool_identifier(p) in selected]
        if strategy=="all_except":
            return [p for p in pools if pool_identifier(p) not in excluded]
        return pools

    def effective_pool_worker_ids(self):
        records=self.effective_pool_records()
        if not records and self.pool_assignment_strategy_key()=="all" and not self.api_pools:
            return [worker_identifier(w) for w in self.available_workers if worker_identifier(w)]
        result=[]
        for pool in records:
            for worker_id in self.worker_pools.get(pool_display_name(pool),[]):
                worker_id=str(worker_id or "").strip()
                if worker_id and worker_id not in result: result.append(worker_id)
        return result



    def active_pool_workers(self):
        ids=set(self.effective_pool_worker_ids())
        if not ids and not self.api_pools and self.pool_assignment_strategy_key()=="all":
            return list(self.available_workers)
        return [w for w in self.available_workers if worker_identifier(w) in ids]

    def worker_data_is_stale(self,max_age_seconds=300):
        if self.worker_target_last_sync is None: return True
        return (datetime.datetime.now()-self.worker_target_last_sync).total_seconds()>float(max_age_seconds)

    def online_pool_workers(self):
        return [w for w in self.active_pool_workers() if worker_is_online(w)]

    def resource_requirements(self):
        def value(name):
            widget = _WIDGETS.get(name)
            if hasattr(widget, "value"):
                try:
                    return int(widget.value())
                except (TypeError, ValueError):
                    return 0
            return 0

        return {
            "minimum_cores": value("rh_minimum_cores"),
            "minimum_ram_gb": value("rh_minimum_ram_gb"),
            "minimum_gpus": value("rh_minimum_gpus"),
        }

    def eligible_workers(self):
        requirements = self.resource_requirements()
        return [
            worker
            for worker in self.online_pool_workers()
            if worker_meets_requirements(worker, **requirements)
        ]

    def eligible_worker_ids(self):
        return [worker_identifier(w) for w in self.eligible_workers() if worker_identifier(w)]

    def update_pool_selection_widgets(self):
        for name in ("rh_selected_pools","rh_excluded_pools"):
            widget=_WIDGETS.get(name)
            if isinstance(widget,PoolMultiSelect):
                widget.set_pools(self.api_pools,self.worker_pools,self.available_workers)

    def update_worker_sync_chips(self):
        api_chip=_WIDGETS.get("worker_api_chip")
        worker_chip=_WIDGETS.get("worker_count_chip")
        pool_chip=_WIDGETS.get("worker_pool_count_chip")
        time_chip=_WIDGETS.get("worker_sync_time_chip")
        total=len(self.available_workers)
        online=len([w for w in self.available_workers if worker_is_online(w)])
        pools=len(self.api_pools)
        syncing=self.worker_sync_thread is not None and self.worker_sync_thread.isRunning()
        if isinstance(api_chip,WorkerStatusChip):
            if syncing: api_chip.set_state("Connecting…",COLORS["info"])
            elif self.worker_target_sync_error: api_chip.set_state("Backend Offline",COLORS["error"])
            elif self.worker_target_has_sync: api_chip.set_state("Backend Online",COLORS["success"])
            else: api_chip.set_state("Not Connected",COLORS["warning"])
        if isinstance(worker_chip,WorkerStatusChip):
            worker_chip.set_state("{} / {} Workers".format(online,total) if total else "0 Workers",
                                  COLORS["success"] if online else COLORS["warning"])
        if isinstance(pool_chip,WorkerStatusChip):
            pool_chip.set_state("{} Pool{}".format(pools,"" if pools==1 else "s"),
                                COLORS["info"] if pools else COLORS["muted"])
        if isinstance(time_chip,WorkerStatusChip):
            if self.worker_target_last_sync is None: time_chip.set_state("Not Synced",COLORS["muted"])
            else:
                prefix="Cached" if self.worker_target_sync_error else ("Stale" if self.worker_data_is_stale() else "Synced")
                time_chip.set_state("{} {}".format(prefix,self.worker_target_last_sync.strftime("%H:%M")),
                                    COLORS["warning"] if prefix in ("Cached","Stale") else COLORS["secondary"])

    def update_worker_targeting_summary(self,*args):
        label=_WIDGETS.get("worker_eligibility_summary")
        if not isinstance(label,QtWidgets.QLabel): return
        strategy=self.pool_assignment_strategy_key()
        effective=self.effective_pool_records()
        online=len(self.online_pool_workers())
        eligible=len(self.eligible_workers())
        if strategy=="all" and not self.api_pools:
            summary="All workers · {} eligible / {} online".format(eligible, online)
        else:
            summary="{} pool{} · {} eligible / {} online".format(
                len(effective),"" if len(effective)==1 else "s",eligible,online
            )
        if not self.worker_target_has_sync:
            detail="Refresh pools before submitting."; color=COLORS["warning"]
        elif self.worker_target_sync_error:
            detail="Showing the last successful pool snapshot."; color=COLORS["warning"]
        elif strategy=="selected" and not self.selected_pool_ids():
            detail="Select at least one pool."; color=COLORS["error"]
        elif strategy=="all_except" and not effective:
            detail="Every pool is excluded."; color=COLORS["error"]
        elif online==0:
            detail="No online workers are available in the targeted pools."; color=COLORS["error"]
        elif eligible==0:
            detail="No online workers match the CPU/RAM/GPU requirements."; color=COLORS["error"]
        else:
            detail="Ready for submission."; color=COLORS["success"]
        label.setText("{}  —  {}".format(summary,detail))
        label.setStyleSheet(
            "QLabel#EligibilitySummary {background-color:%s;border:1px solid %s;border-radius:6px;"
            "color:%s;padding:7px 9px;font-weight:600;}"%(COLORS["surface2"],color,color)
        )

    def update_pool_strategy_ui(self):
        strategy=self.pool_assignment_strategy_key()
        selected=_WIDGETS.get("pool_selected_field")
        excluded=_WIDGETS.get("pool_excluded_field")
        if isinstance(selected,QtWidgets.QWidget): selected.setVisible(strategy=="selected")
        if isinstance(excluded,QtWidgets.QWidget): excluded.setVisible(strategy=="all_except")
        self.update_worker_targeting_summary()

    def on_pool_strategy_changed(self,mode=""):
        self.update_pool_strategy_ui()

    def on_selected_pools_changed(self):
        selected=set(self.selected_pool_ids())
        excluded=self.excluded_pool_ids()
        clean=[v for v in excluded if v not in selected]
        if clean!=excluded: _set_list("rh_excluded_pools",clean)
        self.update_worker_targeting_summary()

    def on_excluded_pools_changed(self):
        excluded=set(self.excluded_pool_ids())
        selected=self.selected_pool_ids()
        clean=[v for v in selected if v not in excluded]
        if clean!=selected: _set_list("rh_selected_pools",clean)
        self.update_worker_targeting_summary()



    def worker_provider(self):
        snapshot = getattr(self.api, "get_worker_targeting_snapshot", None)
        if callable(snapshot):
            return snapshot

        method_names = (
            "get_available_workers",
            "list_available_workers",
            "get_workers",
            "list_workers",
        )

        for method_name in method_names:
            method = getattr(self.api, method_name, None)
            if callable(method):
                return method

        for attribute_name in (
            "AVAILABLE_WORKERS",
            "available_workers",
        ):
            value = getattr(self.api, attribute_name, None)
            if value is not None:
                return lambda workers=value: workers

        return None

    def normalize_workers(self, payload):
        if isinstance(payload, dict):
            for key in ("workers", "items", "data", "results"):
                candidate = payload.get(key)
                if isinstance(candidate, (list, tuple)):
                    payload = candidate
                    break
            else:
                payload = []

        if not isinstance(payload, (list, tuple)):
            payload = []

        workers = []
        seen = set()

        for entry in payload:
            if isinstance(entry, str):
                worker_id = entry.strip()
                hostname = worker_id
                label = worker_id
                status = "ONLINE"
                available = True
                raw = {}
            elif isinstance(entry, dict):
                raw = dict(entry)
                backend_id = str(
                    entry.get("id")
                    or entry.get("worker_id")
                    or ""
                ).strip()
                hostname = str(
                    entry.get("hostname")
                    or entry.get("machine_name")
                    or entry.get("display_name")
                    or entry.get("name")
                    or ""
                ).strip()
                worker_id = backend_id or hostname
                label = hostname or (
                    "Worker {}".format(backend_id)
                    if backend_id
                    else "Unnamed Worker"
                )
                status = str(
                    entry.get("status")
                    or entry.get("state")
                    or ""
                ).strip().upper()

                available_value = entry.get("available")
                if available_value is None:
                    available_value = entry.get("online")

                available = (
                    status not in (
                        "OFFLINE",
                        "DISCONNECTED",
                        "DISABLED",
                    )
                    if available_value is None
                    else bool(available_value)
                )
            else:
                continue

            if not worker_id or worker_id in seen:
                continue

            worker_pools = []
            if isinstance(entry, dict):
                for pool in entry.get("pools") or []:
                    if isinstance(pool, dict):
                        pool_id = str(pool.get("id") or "").strip()
                        pool_name = str(pool.get("name") or "").strip()
                        if pool_id or pool_name:
                            worker_pools.append({
                                "id": pool_id,
                                "name": pool_name,
                                "description": str(
                                    pool.get("description") or ""
                                ),
                            })

            normalized = {
                "id": worker_id,
                "hostname": hostname or label,
                "label": label or worker_id,
                "status": status or (
                    "ONLINE"
                    if available
                    else "OFFLINE"
                ),
                "available": bool(available),
                "pools": worker_pools,
                "ip_address": (
                    str(raw.get("ip_address") or "")
                    if isinstance(raw, dict)
                    else ""
                ),
                "cores": (
                    raw.get("cores")
                    if isinstance(raw, dict)
                    else None
                ),
                "memory_mb": (
                    raw.get("memory_mb")
                    if isinstance(raw, dict)
                    else None
                ),
                "ram_gb": (
                    raw.get("ram_gb")
                    if isinstance(raw, dict)
                    else None
                ),
                "vram_gb": (
                    raw.get("vram_gb")
                    if isinstance(raw, dict)
                    else None
                ),
                "gpu_models": (
                    raw.get("gpu_models") or []
                    if isinstance(raw, dict)
                    else []
                ),
                "system_info": (
                    raw.get("system_info") or {}
                    if isinstance(raw, dict)
                    else {}
                ),
                "last_ping": (
                    str(raw.get("last_ping") or "")
                    if isinstance(raw, dict)
                    else ""
                ),
                "tags": (
                    list(raw.get("tags") or [])
                    if isinstance(raw, dict)
                    else []
                ),
            }

            seen.add(worker_id)
            workers.append(normalized)

        workers.sort(
            key=lambda item: item["label"].lower()
        )
        return workers

    def sync_available_workers(self, *args):
        if self._is_closing:
            return

        provider = self.worker_provider()
        button = _WIDGETS.get("sync_workers_button")

        if provider is None:
            self.worker_target_sync_error = (
                "The current API does not expose worker targeting endpoints."
            )
            self.update_worker_sync_chips()
            self.update_worker_targeting_summary()
            return

        if self.worker_sync_thread is not None:
            if self.worker_sync_thread.isRunning():
                return

        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(False)
            button.setText("Refreshing…")

        self.worker_target_sync_error = ""
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()

        self.worker_sync_thread = WorkerSyncThread(
            provider,
            parent=self,
        )
        self.worker_sync_thread.succeeded.connect(
            self.on_workers_synced
        )
        self.worker_sync_thread.failed.connect(
            self.on_worker_sync_failed
        )
        self.worker_sync_thread.finished.connect(
            self.on_worker_sync_finished
        )
        self.worker_sync_thread.start()

    def on_workers_synced(self, payload):
        pools_payload = None
        workers_payload = payload

        if isinstance(payload, dict) and (
            "workers" in payload or "pools" in payload
        ):
            workers_payload = payload.get("workers") or []
            pools_payload = payload.get("pools") or []

        workers = self.normalize_workers(workers_payload)
        pools = (
            self.normalize_pools(pools_payload)
            if pools_payload is not None
            else None
        )

        self.worker_target_last_sync = datetime.datetime.now()
        self.worker_target_has_sync = True
        self.worker_target_sync_error = ""

        self.apply_available_workers(
            workers,
            pools=pools,
        )
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()

        online_count = len([
            worker
            for worker in workers
            if worker_is_online(worker)
        ])

        self.append_activity(
            "Worker target sync completed: {} online / {} total, "
            "{} backend pool(s).".format(
                online_count,
                len(workers),
                len(self.api_pools),
            )
        )

    def on_worker_sync_failed(self, error):
        self.worker_target_sync_error = str(error or "Unknown error")
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()

        cached_note = (
            " Showing the last successful snapshot."
            if self.available_workers or self.api_pools
            else ""
        )

        self.set_status(
            "Worker sync failed.{}".format(cached_note),
            level="warning",
        )
        self.append_activity(
            "Worker sync failed: {}{}".format(
                error,
                cached_note,
            )
        )

    def on_worker_sync_finished(self):
        if self._is_closing:
            return

        button = _WIDGETS.get("sync_workers_button")

        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(True)
            button.setText("Refresh")

        if self.worker_sync_thread is not None:
            self.worker_sync_thread.deleteLater()
            self.worker_sync_thread = None

    def apply_available_workers(self, workers, pools=None):
        normalized = self.normalize_workers(workers)
        self.available_workers = normalized

        if pools is not None:
            normalized_pools = self.normalize_pools(pools)
            self.api_pools = normalized_pools
            memberships = {
                pool["name"]: []
                for pool in normalized_pools
            }
            names_by_id = {
                str(pool.get("id") or ""): pool["name"]
                for pool in normalized_pools
                if str(pool.get("id") or "")
            }

            for worker in normalized:
                worker_id = str(worker.get("id") or "")
                for pool in worker.get("pools") or []:
                    pool_id = str(pool.get("id") or "")
                    pool_name = str(pool.get("name") or "") or names_by_id.get(pool_id, "")
                    if pool_name and pool_name in memberships and worker_id:
                        if worker_id not in memberships[pool_name]:
                            memberships[pool_name].append(worker_id)

            self.worker_pools = memberships
            self.save_worker_pools()

        self.update_pool_selection_widgets()
        self.apply_pending_pool_scene_state()
        self.update_pool_strategy_ui()
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()
        self.save_scene_state(force=True)


