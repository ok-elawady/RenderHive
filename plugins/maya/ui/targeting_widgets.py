from __future__ import absolute_import

import os

from .qt_compat import QtCore, QtGui, QtWidgets
from .icons import get_icon, icon_path
from .qt_theme import COLORS, build_stylesheet
from .worker_data import (
    format_gb,
    pool_display_name,
    pool_identifier,
    worker_display_name,
    worker_gpu_text,
    worker_identifier,
    worker_is_online,
    worker_memory_gb,
    worker_status,
)


class PoolSelectionDialog(QtWidgets.QDialog):
    """Modern pool targeting dialog matching Worker/Frontend modal design tokens."""

    def __init__(
        self,
        title,
        pools,
        memberships,
        workers,
        selected_values,
        parent=None,
    ):
        super(PoolSelectionDialog, self).__init__(parent)
        self.setObjectName("RenderHiveDialog")
        self.setWindowTitle(title or "Select Target Pools")
        self.setModal(True)
        self.setMinimumSize(780, 520)
        self.resize(880, 580)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)

        # Window icon
        _icon_path = icon_path("renderhive_header_logo.png")
        if os.path.isfile(_icon_path):
            self.setWindowIcon(QtGui.QIcon(_icon_path))

        self.setStyleSheet(build_stylesheet())

        self._pools = list(pools or [])
        self._memberships = dict(memberships or {})
        self._workers = list(workers or [])
        self._selected = set(
            str(value)
            for value in (selected_values or [])
        )
        self._items = []

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header (#0B0E17 matching DWM Titlebar & Frontend SheetHeader) ──
        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("DialogHeader")
        header_layout = QtWidgets.QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(12)
        header_layout.setAlignment(QtCore.Qt.AlignVCenter)

        title_col = QtWidgets.QVBoxLayout()
        title_col.setSpacing(2)
        title_label = QtWidgets.QLabel(title or "Select Target Pools")
        title_label.setObjectName("PageTitle")
        subtitle_label = QtWidgets.QLabel(
            "Select backend pools for job dispatch. Expand any pool to inspect assigned nodes and hardware telemetry."
        )
        subtitle_label.setObjectName("CardDescription")
        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)
        header_layout.addLayout(title_col, 1)

        self.header_badge = QtWidgets.QLabel("0 pools selected")
        self.header_badge.setObjectName("MetaChip")
        header_layout.addWidget(self.header_badge)

        root.addWidget(header_frame)

        # ── Body Content Container ──
        body_container = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body_container)
        body_layout.setContentsMargins(18, 14, 18, 14)
        body_layout.setSpacing(10)

        # Search & Toolbar Row
        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search pools, workers, status or hardware…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(32)
        self.search.textChanged.connect(self.filter_items)
        search_row.addWidget(self.search, 1)

        select_all_btn = QtWidgets.QPushButton("  Select All")
        select_all_btn.setObjectName("SecondaryBtn")
        select_all_btn.setIcon(get_icon("check-square", "#CBD5E1", 13))
        select_all_btn.setFixedHeight(32)
        select_all_btn.setCursor(QtCore.Qt.PointingHandCursor)
        select_all_btn.clicked.connect(self.select_all)
        search_row.addWidget(select_all_btn)

        clear_btn = QtWidgets.QPushButton("  Clear")
        clear_btn.setObjectName("SecondaryBtn")
        clear_btn.setIcon(get_icon("x", "#CBD5E1", 13))
        clear_btn.setFixedHeight(32)
        clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_all)
        search_row.addWidget(clear_btn)

        expand_btn = QtWidgets.QPushButton("  Expand All")
        expand_btn.setObjectName("SecondaryBtn")
        expand_btn.setIcon(get_icon("chevrons-down", "#CBD5E1", 13))
        expand_btn.setFixedHeight(32)
        expand_btn.setCursor(QtCore.Qt.PointingHandCursor)
        search_row.addWidget(expand_btn)

        collapse_btn = QtWidgets.QPushButton("  Collapse All")
        collapse_btn.setObjectName("SecondaryBtn")
        collapse_btn.setIcon(get_icon("chevrons-up", "#CBD5E1", 13))
        collapse_btn.setFixedHeight(32)
        collapse_btn.setCursor(QtCore.Qt.PointingHandCursor)
        search_row.addWidget(collapse_btn)

        body_layout.addLayout(search_row)

        # Tree Container
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("JobDependencyTree")
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels([
            "Pool / Worker Node",
            "Status",
            "RAM",
            "GPU",
            "Description / Hardware Details",
        ])
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.tree.itemChanged.connect(self._on_item_changed)
        body_layout.addWidget(self.tree, 1)

        expand_btn.clicked.connect(self.tree.expandAll)
        collapse_btn.clicked.connect(self.tree.collapseAll)

        root.addWidget(body_container, 1)

        # ── Populate Items ──
        workers_by_id = {
            worker_identifier(worker): worker
            for worker in self._workers
            if worker_identifier(worker)
        }

        for pool in self._pools:
            pool_id = pool_identifier(pool)
            name = pool_display_name(pool)

            if not pool_id:
                continue

            member_ids = list(self._memberships.get(name, []))
            online = sum(
                1
                for worker_id in member_ids
                if (
                    worker_id in workers_by_id
                    and worker_is_online(workers_by_id[worker_id])
                )
            )

            pool_item = QtWidgets.QTreeWidgetItem([
                name,
                "{} online / {}".format(online, len(member_ids)),
                "—",
                "—",
                str(pool.get("description") or "Standard worker pool"),
            ])
            pool_item.setData(0, QtCore.Qt.UserRole, pool_id)
            pool_item.setData(0, QtCore.Qt.UserRole + 1, "pool")
            pool_item.setFlags(pool_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            pool_item.setCheckState(
                0,
                QtCore.Qt.Checked
                if (pool_id in self._selected or name in self._selected)
                else QtCore.Qt.Unchecked,
            )
            pool_item.setForeground(
                1,
                QtGui.QBrush(QtGui.QColor(COLORS["success"] if online else COLORS["muted"])),
            )

            if member_ids:
                for worker_id in member_ids:
                    worker = workers_by_id.get(worker_id)
                    if worker is None:
                        worker_item = QtWidgets.QTreeWidgetItem([
                            str(worker_id),
                            "Unavailable",
                            "—",
                            "—",
                            "Worker details were not returned by the API.",
                        ])
                        worker_item.setForeground(
                            1,
                            QtGui.QBrush(QtGui.QColor(COLORS["muted"])),
                        )
                    else:
                        status = worker_status(worker) or "UNKNOWN"
                        online_worker = worker_is_online(worker)
                        ip_address = str(worker.get("ip_address") or "").strip()
                        last_ping = str(worker.get("last_ping") or "").strip()

                        details = []
                        if ip_address:
                            details.append("IP {}".format(ip_address))
                        if last_ping:
                            details.append("Last ping {}".format(last_ping))

                        worker_item = QtWidgets.QTreeWidgetItem([
                            worker_display_name(worker),
                            status.replace("_", " ").title(),
                            format_gb(worker_memory_gb(worker)),
                            worker_gpu_text(worker),
                            " · ".join(details) or "—",
                        ])

                        status_color = (
                            COLORS["info"]
                            if status in ("RENDERING", "BUSY", "WORKING")
                            else (COLORS["success"] if online_worker else COLORS["muted"])
                        )
                        worker_item.setForeground(
                            1,
                            QtGui.QBrush(QtGui.QColor(status_color)),
                        )

                    worker_item.setData(0, QtCore.Qt.UserRole, str(worker_id))
                    worker_item.setData(0, QtCore.Qt.UserRole + 1, "worker")
                    worker_item.setFlags(worker_item.flags() & ~QtCore.Qt.ItemIsUserCheckable)
                    pool_item.addChild(worker_item)
            else:
                empty_item = QtWidgets.QTreeWidgetItem([
                    "No workers assigned",
                    "—",
                    "—",
                    "—",
                    "Pool membership is managed by RenderHive.",
                ])
                empty_item.setData(0, QtCore.Qt.UserRole + 1, "empty")
                empty_item.setFlags(QtCore.Qt.NoItemFlags)
                empty_item.setForeground(0, QtGui.QBrush(QtGui.QColor(COLORS["muted"])))
                pool_item.addChild(empty_item)

            self.tree.addTopLevelItem(pool_item)
            self._items.append(pool_item)

        if not self._items:
            item = QtWidgets.QTreeWidgetItem([
                "No backend pools available.",
                "—",
                "—",
                "—",
                "Refresh after pools are created in RenderHive.",
            ])
            item.setFlags(QtCore.Qt.NoItemFlags)
            item.setForeground(0, QtGui.QBrush(QtGui.QColor(COLORS["muted"])))
            self.tree.addTopLevelItem(item)

        # ── Dialog Footer (#0B0E17 matching DWM Titlebar & Worker Dialogs) ──
        footer_frame = QtWidgets.QFrame()
        footer_frame.setObjectName("DialogFooter")
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        footer_layout.setSpacing(8)
        footer_layout.setAlignment(QtCore.Qt.AlignVCenter)

        self.footer_hint = QtWidgets.QLabel("0 pools selected")
        self.footer_hint.setObjectName("MutedText")
        footer_layout.addWidget(self.footer_hint, 1)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        apply_btn = QtWidgets.QPushButton("  Apply Selection")
        apply_btn.setObjectName("SubmitButton")
        apply_btn.setIcon(get_icon("check", COLORS["primary_fg"], 13))
        apply_btn.setFixedHeight(32)
        apply_btn.setMinimumWidth(130)
        apply_btn.setCursor(QtCore.Qt.PointingHandCursor)
        apply_btn.clicked.connect(self.accept)
        footer_layout.addWidget(apply_btn)

        root.addWidget(footer_frame)

        self.update_selection_counter()

    def showEvent(self, event):
        super(PoolSelectionDialog, self).showEvent(event)
        self._apply_window_theme()

    def _apply_window_theme(self):
        """Match native OS titlebar and window border to studio dark theme (#0B0E17)."""
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            import ctypes.wintypes as wintypes
            hwnd = wintypes.HWND(int(self.winId()))
            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(ctypes.c_int(0x00170E0B)), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, ctypes.byref(ctypes.c_int(0x00E1D5CB)), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 34, ctypes.byref(ctypes.c_int(0x0036251E)), 4)
        except Exception:
            pass

    def _on_item_changed(self, item, column):
        if column == 0:
            self.update_selection_counter()

    def update_selection_counter(self):
        count = len(self.selected_values())
        total = len(self._items)
        badge_text = "{} pool{} selected".format(count, "s" if count != 1 else "")
        hint_text = "{} of {} pool{} selected for dispatch".format(
            count, total, "s" if total != 1 else ""
        )
        if hasattr(self, "header_badge"):
            self.header_badge.setText(badge_text)
        if hasattr(self, "footer_hint"):
            self.footer_hint.setText(hint_text)

    @staticmethod
    def item_search_text(item):
        return " ".join(
            item.text(column)
            for column in range(item.columnCount())
        ).lower()

    def filter_items(self, value):
        query = str(value or "").strip().lower()

        for pool_item in self._items:
            if not query:
                pool_item.setHidden(False)
                for index in range(pool_item.childCount()):
                    pool_item.child(index).setHidden(False)
                continue

            pool_match = query in self.item_search_text(pool_item)
            child_match = False

            for index in range(pool_item.childCount()):
                child = pool_item.child(index)
                matches = query in self.item_search_text(child)
                child.setHidden(not (pool_match or matches))
                child_match = child_match or matches

            pool_item.setHidden(not (pool_match or child_match))

            if child_match and not pool_match:
                pool_item.setExpanded(True)

    def select_all(self):
        self.tree.blockSignals(True)
        for item in self._items:
            if not item.isHidden():
                item.setCheckState(0, QtCore.Qt.Checked)
        self.tree.blockSignals(False)
        self.update_selection_counter()

    def clear_all(self):
        self.tree.blockSignals(True)
        for item in self._items:
            item.setCheckState(0, QtCore.Qt.Unchecked)
        self.tree.blockSignals(False)
        self.update_selection_counter()

    def selected_values(self):
        values = []

        for item in self._items:
            if item.checkState(0) == QtCore.Qt.Checked:
                value = str(
                    item.data(0, QtCore.Qt.UserRole) or ""
                ).strip()

                if value and value not in values:
                    values.append(value)

        return values

class PoolMultiSelect(QtWidgets.QPushButton):
    selectionChanged = QtCore.Signal()

    def __init__(self, title, empty_text, parent=None):
        super(PoolMultiSelect,self).__init__(parent)
        self.setObjectName("SecondaryBtn")
        self._title=str(title)
        self._empty_text=str(empty_text)
        self._pools=[]
        self._memberships={}
        self._workers=[]
        self._selected_values=[]
        self.setFixedHeight(34)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.clicked.connect(self.open_selector)
        self.update_summary()

    def set_pools(self,pools,memberships=None,workers=None):
        self._pools=list(pools or [])
        self._memberships=dict(memberships or {})
        self._workers=list(workers or [])
        ids={pool_identifier(p) for p in self._pools if pool_identifier(p)}
        names={pool_display_name(p):pool_identifier(p) for p in self._pools if pool_identifier(p)}
        clean=[]
        for value in self._selected_values:
            value=names.get(value,value)
            if value in ids and value not in clean:
                clean.append(value)
        self._selected_values=clean
        self.update_summary()

    def selected_values(self):
        return list(self._selected_values)

    def set_selected_values(self,values):
        ids={pool_identifier(p) for p in self._pools if pool_identifier(p)}
        names={pool_display_name(p):pool_identifier(p) for p in self._pools if pool_identifier(p)}
        clean=[]
        for value in values or []:
            value=str(value or "").strip()
            value=names.get(value,value)
            if value and (not ids or value in ids) and value not in clean:
                clean.append(value)
        if clean==self._selected_values:
            self.update_summary(); return
        self._selected_values=clean
        self.update_summary()
        self.selectionChanged.emit()

    def open_selector(self):
        dialog=PoolSelectionDialog(
            self._title,self._pools,self._memberships,self._workers,
            self._selected_values,parent=self.window()
        )
        if dialog.exec_()!=QtWidgets.QDialog.Accepted:
            return
        self._selected_values=dialog.selected_values()
        self.update_summary()
        self.selectionChanged.emit()

    def update_summary(self):
        count=len(self._selected_values)
        if not count:
            self.setText(self._empty_text); return
        names={pool_identifier(p):pool_display_name(p) for p in self._pools}
        labels=[names.get(value,value) for value in self._selected_values]
        if count==1:
            self.setText(labels[0])
        elif count<=3:
            self.setText(", ".join(labels))
        else:
            self.setText("{} pools selected".format(count))

class RenderLayerSelector(QtWidgets.QFrame):
    """Compact multi-select for Maya Render Setup/legacy render layers."""

    selectionChanged = QtCore.Signal()
    refreshRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super(RenderLayerSelector, self).__init__(parent)
        self._records = []
        self._selection_initialized = False
        self._updating = False
        self.setObjectName("RenderLayerSelector")
        self.setAutoFillBackground(False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        tools = QtWidgets.QHBoxLayout()
        tools.setSpacing(6)

        self.summary = QtWidgets.QLabel("No render layers detected")
        self.summary.setObjectName("SecondaryText")
        tools.addWidget(self.summary)
        tools.addStretch()

        renderable_button = QtWidgets.QPushButton("Scene Renderable")
        renderable_button.setObjectName("GhostButton")
        renderable_button.clicked.connect(self.select_renderable)
        tools.addWidget(renderable_button)

        all_button = QtWidgets.QPushButton("All")
        all_button.setObjectName("GhostButton")
        all_button.clicked.connect(self.select_all)
        tools.addWidget(all_button)

        none_button = QtWidgets.QPushButton("None")
        none_button.setObjectName("GhostButton")
        none_button.clicked.connect(self.clear_all)
        tools.addWidget(none_button)

        refresh_button = QtWidgets.QPushButton("Refresh")
        refresh_button.setObjectName("InfoButton")
        refresh_button.clicked.connect(lambda _checked=False: self.refreshRequested.emit())
        tools.addWidget(refresh_button)
        layout.addLayout(tools)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("RenderLayerTree")
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Render Layer", "Scene State"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.tree.setMinimumHeight(132)
        self.tree.setMaximumHeight(210)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)

    def set_layers(self, records):
        previous = self.selected_values() if self._selection_initialized else []

        # Treat the visible selector as the single source of truth. Maya can
        # expose the same logical layer through Render Setup and legacy
        # renderLayer APIs, so collapse duplicate names before building rows.
        clean_records = []
        seen_names = set()
        for raw in records or []:
            if not isinstance(raw, dict):
                continue
            record = dict(raw)
            name = str(record.get("name") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            record["name"] = name
            clean_records.append(record)

        self._records = clean_records
        available = {str(item.get("name") or "") for item in self._records}
        selected = {value for value in previous if value in available}

        if not self._selection_initialized:
            # First-open convenience only: use Maya's renderable state. When
            # custom Render Setup layers exist, defaultRenderLayer is reported
            # disabled by the bridge and is therefore not selected implicitly.
            selected = {
                str(item.get("name") or "")
                for item in self._records
                if item.get("renderable")
            }
            if not selected:
                for item in self._records:
                    if item.get("is_current") or item.get("is_default"):
                        selected.add(str(item.get("name") or ""))
                        break
            if not selected and self._records:
                selected.add(str(self._records[0].get("name") or ""))
            self._selection_initialized = True

        self._updating = True
        self.tree.clear()
        for record in self._records:
            name = str(record.get("name") or "").strip()
            if not name:
                continue
            label = str(record.get("display_name") or name)
            if record.get("is_current"):
                label += "  •  Active"

            status = "Renderable" if record.get("renderable") else "Disabled in Scene"
            item = QtWidgets.QTreeWidgetItem([label, status])
            item.setData(0, QtCore.Qt.UserRole, name)
            item.setData(1, QtCore.Qt.UserRole, dict(record))
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemIsUserCheckable
                | QtCore.Qt.ItemIsEnabled
            )
            item.setCheckState(
                0,
                QtCore.Qt.Checked if name in selected else QtCore.Qt.Unchecked,
            )
            self.tree.addTopLevelItem(item)
        self._updating = False
        self._update_summary()

    def selected_values(self):
        result = []
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.checkState(0) != QtCore.Qt.Checked:
                continue
            value = str(item.data(0, QtCore.Qt.UserRole) or "").strip()
            if value and value not in result:
                result.append(value)
        return result

    def selected_records(self):
        selected = set(self.selected_values())
        return [
            dict(item) for item in self._records
            if str(item.get("name") or "") in selected
        ]

    def set_selected_values(self, values):
        selected = {str(value or "").strip() for value in (values or []) if str(value or "").strip()}
        self._selection_initialized = True
        self._updating = True
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            name = str(item.data(0, QtCore.Qt.UserRole) or "")
            item.setCheckState(
                0,
                QtCore.Qt.Checked if name in selected else QtCore.Qt.Unchecked,
            )
        self._updating = False
        self._update_summary()

    def select_renderable(self):
        renderable = {
            str(item.get("name") or "")
            for item in self._records
            if item.get("renderable")
        }
        self.set_selected_values(renderable)
        self.selectionChanged.emit()

    def select_all(self):
        self.set_selected_values(
            [item.get("name") for item in self._records]
        )
        self.selectionChanged.emit()

    def clear_all(self):
        self.set_selected_values([])
        self.selectionChanged.emit()

    def _on_item_changed(self, item, column):
        if self._updating or column != 0:
            return
        self._selection_initialized = True
        self._update_summary()
        self.selectionChanged.emit()

    def _update_summary(self):
        selected = len(self.selected_values())
        total = len(self._records)
        if total:
            self.summary.setText(
                "{} Selected / {} Available".format(selected, total)
            )
        else:
            self.summary.setText("No render layers detected")




class WorkerSyncThread(QtCore.QThread):
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, provider, parent=None):
        super(WorkerSyncThread, self).__init__(parent)
        self.provider = provider

    def run(self):
        if self.isInterruptionRequested():
            return

        try:
            result = self.provider()
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))
