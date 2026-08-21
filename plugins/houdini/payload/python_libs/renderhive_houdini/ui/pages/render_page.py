"""Production Houdini render-source selection and per-source submission settings."""

from __future__ import absolute_import

import os
import re

from renderhive_houdini.ui.qt_compat import (
    QtWidgets,
    Signal,
    USER_ROLE,
    CHECKED,
    UNCHECKED,
    ITEM_IS_ENABLED,
    ITEM_IS_SELECTABLE,
    ITEM_IS_USER_CHECKABLE,
    SINGLE_SELECTION,
    HEADER_STRETCH,
    HEADER_RESIZE_TO_CONTENTS,
)
from renderhive_houdini.ui.widgets import PageHeader, SectionCard, LabeledField, ReadOnlyRow, InlineStatus


_FORMATS = ("EXR", "PNG", "JPG", "TIFF", "TGA", "BMP", "RAT")


def _padding(path):
    value = str(path or "")
    matches = re.findall(r"\$F(\d*)", value, re.IGNORECASE)
    if matches:
        return int(matches[-1] or 1)
    match = re.search(r"%0?(\d+)d", value)
    if match:
        return int(match.group(1))
    hashes = re.findall(r"(#+)", value)
    return len(hashes[-1]) if hashes else 0


def _split_output(path, fallback_prefix="houdini_job"):
    path = str(path or "").strip()
    directory = os.path.dirname(path) if path else ""
    filename = os.path.basename(path) if path else ""
    stem, extension = os.path.splitext(filename)
    stem = re.sub(r"(?:[._-]?\$F\d*|[._-]?%0?\d*d|[._-]?#+)$", "", stem, flags=re.IGNORECASE)
    return {
        "directory": directory,
        "prefix": stem or fallback_prefix,
        "format": extension.lower().lstrip(".").upper() or "EXR",
        "padding": _padding(path),
    }


def _contains_frame_token(value):
    value = str(value or "")
    return bool(re.search(r"\$F\d*", value, re.IGNORECASE) or re.search(r"%0?\d*d", value) or "#" in value)


def _compose_output(directory, prefix, file_format, padding):
    directory = str(directory or "").strip()
    prefix = str(prefix or "houdini_job").strip() or "houdini_job"
    extension = str(file_format or "EXR").strip().lower().lstrip(".") or "exr"
    padding = max(0, int(padding or 0))
    filename = prefix
    if padding and not _contains_frame_token(filename):
        filename += ".$F{}".format(padding)
    if not filename.lower().endswith("." + extension):
        filename += "." + extension
    return os.path.join(directory, filename) if directory else filename


def _frame_text(node):
    if node is None:
        return "—"
    start = getattr(node, "frame_start", 1)
    end = getattr(node, "frame_end", start)
    step = getattr(node, "frame_step", 1)
    def fmt(value):
        try:
            f = float(value)
            return str(int(f)) if f.is_integer() else str(f)
        except Exception:
            return str(value)
    return "{}-{} x{}".format(fmt(start), fmt(end), fmt(step))


class RenderPage(QtWidgets.QWidget):
    refreshRequested = Signal()
    useSelectedRequested = Signal()
    renderNodeChanged = Signal(object)
    renderSelectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes = []
        self._context = None
        self._scene_key = ""
        self._applying_node = False
        self._selected_paths = set()
        self._pending_selected_paths = []

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        root.addWidget(PageHeader(
            "Render Configuration",
            "Choose one or more executable Houdini render sources. Each checked source becomes a backend RenderHive layer.",
        ))

        preset = SectionCard("Render Preset", "Apply a common output resolution and format to the currently focused render source.")
        preset_row = QtWidgets.QHBoxLayout()
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItems(("Manual Configuration", "Preview", "HD", "Full HD", "Production EXR", "4K Production EXR"))
        self.apply_preset_button = QtWidgets.QPushButton("Apply Preset")
        self.apply_preset_button.setObjectName("PrimaryButton")
        self.apply_preset_button.clicked.connect(self.apply_preset)
        preset_row.addWidget(self.preset_combo, 1); preset_row.addWidget(self.apply_preset_button)
        preset.layout.addLayout(preset_row)

        source = SectionCard("Render Sources", "Checked ROP/Solaris nodes are submitted as independent backend layers inside one job.")
        selector = QtWidgets.QHBoxLayout(); selector.setSpacing(8)
        self.node_combo = QtWidgets.QComboBox(); self.node_combo.setMinimumWidth(330)
        self.node_combo.currentIndexChanged.connect(self._on_node_changed)
        self.refresh_button = QtWidgets.QPushButton("Refresh Nodes")
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.selected_button = QtWidgets.QPushButton("Use Selected Node")
        self.selected_button.setObjectName("PrimaryButton")
        self.selected_button.clicked.connect(self.useSelectedRequested.emit)
        selector.addWidget(self.node_combo, 1); selector.addWidget(self.refresh_button); selector.addWidget(self.selected_button)
        source.layout.addLayout(selector)

        self.source_tree = QtWidgets.QTreeWidget()
        self.source_tree.setObjectName("RenderLayerTree")
        self.source_tree.setColumnCount(5)
        self.source_tree.setHeaderLabels(("Render Source", "Renderer", "Mode", "Frames", "Output"))
        self.source_tree.setRootIsDecorated(False)
        self.source_tree.setAlternatingRowColors(True)
        self.source_tree.setSelectionMode(SINGLE_SELECTION)
        self.source_tree.setMinimumHeight(150)
        self.source_tree.header().setSectionResizeMode(0, HEADER_STRETCH)
        self.source_tree.header().setSectionResizeMode(1, HEADER_RESIZE_TO_CONTENTS)
        self.source_tree.header().setSectionResizeMode(2, HEADER_RESIZE_TO_CONTENTS)
        self.source_tree.header().setSectionResizeMode(3, HEADER_RESIZE_TO_CONTENTS)
        self.source_tree.header().setSectionResizeMode(4, HEADER_STRETCH)
        self.source_tree.itemChanged.connect(self._on_source_item_changed)
        self.source_tree.itemSelectionChanged.connect(self._on_source_row_changed)
        self.source_tree.itemDoubleClicked.connect(self._focus_tree_item)
        source.layout.addWidget(self.source_tree)

        source_actions = QtWidgets.QHBoxLayout(); source_actions.setSpacing(7)
        self.selection_label = QtWidgets.QLabel("0 Selected / 0 Available")
        self.selection_label.setObjectName("SecondaryText")
        select_all = QtWidgets.QPushButton("All")
        select_all.setObjectName("GhostButton"); select_all.clicked.connect(lambda: self._set_all_checks("all"))
        select_renderable = QtWidgets.QPushButton("Renderable")
        select_renderable.setObjectName("GhostButton"); select_renderable.clicked.connect(lambda: self._set_all_checks("renderable"))
        clear = QtWidgets.QPushButton("None")
        clear.setObjectName("GhostButton"); clear.clicked.connect(lambda: self._set_all_checks("none"))
        source_actions.addWidget(self.selection_label); source_actions.addStretch(); source_actions.addWidget(select_all); source_actions.addWidget(select_renderable); source_actions.addWidget(clear)
        source.layout.addLayout(source_actions)
        self.node_status = InlineStatus("Open a scene, then refresh or use the selected render node.", "neutral")
        source.layout.addWidget(self.node_status)

        frames = SectionCard("Focused Source Settings", "Edit the currently focused source. Other checked sources keep their native node settings.")
        frame_grid = QtWidgets.QGridLayout(); frame_grid.setHorizontalSpacing(10); frame_grid.setVerticalSpacing(8)
        self.start_frame = QtWidgets.QDoubleSpinBox(); self.start_frame.setRange(-1000000, 1000000); self.start_frame.setDecimals(3)
        self.end_frame = QtWidgets.QDoubleSpinBox(); self.end_frame.setRange(-1000000, 1000000); self.end_frame.setDecimals(3)
        self.frame_step = QtWidgets.QDoubleSpinBox(); self.frame_step.setRange(0.001, 100000); self.frame_step.setDecimals(3); self.frame_step.setValue(1)
        self.renderer = QtWidgets.QComboBox(); self.renderer.currentIndexChanged.connect(self._update_override_state)
        self.camera = QtWidgets.QComboBox(); self.camera.currentIndexChanged.connect(self._update_override_state)
        self.execution = QtWidgets.QLineEdit(); self.execution.setReadOnly(True)
        frame_grid.addWidget(LabeledField("Start Frame", self.start_frame, "First frame submitted for the focused source."), 0, 0)
        frame_grid.addWidget(LabeledField("End Frame", self.end_frame, "Last frame submitted for the focused source."), 0, 1)
        frame_grid.addWidget(LabeledField("Frame Step", self.frame_step, "Increment between submitted frames."), 1, 0)
        frame_grid.addWidget(LabeledField("Renderer", self.renderer, "Renderer detected from the focused Houdini render source."), 1, 1)
        frame_grid.addWidget(LabeledField("Render Camera", self.camera, "Camera detected from /obj or Solaris."), 2, 0)
        frame_grid.addWidget(LabeledField("Execution Mode", self.execution, "Hython drives ROP rendering; USD/Solaris render ROPs can invoke Husk internally."), 2, 1)
        frame_grid.setColumnStretch(0, 1); frame_grid.setColumnStretch(1, 1)
        frames.layout.addLayout(frame_grid)

        output = SectionCard("Focused Source Output", "Keep node settings or send a non-destructive farm override for the focused source.")
        output_grid = QtWidgets.QGridLayout(); output_grid.setHorizontalSpacing(10); output_grid.setVerticalSpacing(8)
        self.output_source = QtWidgets.QComboBox(); self.output_source.addItems(("Use Render Node Settings", "Override for This Job"))
        self.output_source.currentIndexChanged.connect(self._on_output_source_changed)
        output_grid.addWidget(LabeledField("Output Source", self.output_source, "Overrides are sent to the Worker and do not modify the saved HIP file."), 0, 0, 1, 2)
        self.output_directory = QtWidgets.QLineEdit(); self.output_directory.textChanged.connect(self._update_output_preview)
        self.output_browse = QtWidgets.QPushButton("Browse"); self.output_browse.clicked.connect(self.browse_output_directory)
        self.image_prefix = QtWidgets.QLineEdit(); self.image_prefix.textChanged.connect(self._update_output_preview)
        self.file_format = QtWidgets.QComboBox(); self.file_format.addItems(_FORMATS); self.file_format.currentIndexChanged.connect(self._update_output_preview)
        self.frame_padding = QtWidgets.QSpinBox(); self.frame_padding.setRange(0, 20); self.frame_padding.valueChanged.connect(self._update_output_preview)
        self.width = QtWidgets.QSpinBox(); self.width.setRange(0, 100000)
        self.height = QtWidgets.QSpinBox(); self.height.setRange(0, 100000)
        output_dir_widget = QtWidgets.QWidget(); output_dir_widget.setObjectName("InlineFieldContainer")
        output_dir_layout = QtWidgets.QHBoxLayout(output_dir_widget); output_dir_layout.setContentsMargins(0, 0, 0, 0); output_dir_layout.setSpacing(8)
        output_dir_layout.addWidget(self.output_directory, 1); output_dir_layout.addWidget(self.output_browse)
        output_grid.addWidget(LabeledField("Output Directory", output_dir_widget, "Final rendered image directory."), 1, 0, 1, 2)
        output_grid.addWidget(LabeledField("Image Prefix", self.image_prefix), 2, 0)
        output_grid.addWidget(LabeledField("File Format", self.file_format), 2, 1)
        output_grid.addWidget(LabeledField("Frame Padding", self.frame_padding), 3, 0)
        resolution = QtWidgets.QWidget(); resolution.setObjectName("InlineFieldContainer")
        resolution_layout = QtWidgets.QHBoxLayout(resolution); resolution_layout.setContentsMargins(0, 0, 0, 0); resolution_layout.setSpacing(8)
        resolution_layout.addWidget(self.width); resolution_layout.addWidget(self.height)
        output_grid.addWidget(LabeledField("Resolution", resolution), 3, 1)
        output_grid.setColumnStretch(0, 1); output_grid.setColumnStretch(1, 1)
        output.layout.addLayout(output_grid)
        self.output_preview = ReadOnlyRow("Final Image Output", tooltip="Final image path submitted for the focused source.")
        self.usd_output = ReadOnlyRow("Intermediate USD", tooltip="USD generated by a Solaris/USD Render ROP before Husk rendering.")
        self.usd_output.setVisible(False)
        output.layout.addWidget(self.output_preview); output.layout.addWidget(self.usd_output)

        for card in (preset, source, frames, output):
            root.addWidget(card)
        root.addStretch()
        self._set_output_editable(False)

    @staticmethod
    def _context_key(context):
        path = str(getattr(context, "hip_path", "") or "").strip().lower()
        return path or "__untitled__:{}".format(str(getattr(context, "hip_name", "") or ""))

    def has_nodes(self):
        return bool(self._nodes)

    def show_scan_prompt(self):
        if self._nodes:
            return
        self.node_combo.blockSignals(True); self.node_combo.clear(); self.node_combo.addItem("Refresh Nodes or use the selected node"); self.node_combo.setEnabled(False); self.node_combo.blockSignals(False)
        self.source_tree.clear(); self._selected_paths.clear(); self._update_selection_label()
        self.set_node_info(None, prompt=True)

    def set_context(self, context, reset_scene=False):
        new_key = self._context_key(context)
        scene_changed = bool(reset_scene or (self._scene_key and new_key != self._scene_key))
        self._scene_key = new_key; self._context = context
        if scene_changed:
            self._nodes = []; self._selected_paths.clear(); self._pending_selected_paths = []
            self.node_combo.blockSignals(True); self.node_combo.clear(); self.node_combo.blockSignals(False); self.source_tree.clear()
        if self.current_node_info() is None:
            self.start_frame.setValue(context.frame_start); self.end_frame.setValue(context.frame_end); self.frame_step.setValue(1.0)
            self._set_combo_values(self.renderer, ("Select a render node",), "Select a render node")
            self._set_combo_values(self.camera, ("Not Set",), "Not Set")
            self.execution.setText("Automatic")
            default_path = os.path.join(context.output_root or context.hip_directory or "", "{}.$F4.exr".format(context.scene_name or "houdini_job"))
            self._populate_output_fields(default_path, context.scene_name or "houdini_job")
            self.width.setValue(0); self.height.setValue(0); self.usd_output.setVisible(False); self._update_output_preview()
        return scene_changed

    def set_nodes(self, nodes, preferred_path=""):
        previous_checked = set(self.selected_node_paths()) or set(self._pending_selected_paths)
        current_path = preferred_path or self.current_node_path()
        self._nodes = list(nodes or [])
        self.node_combo.blockSignals(True); self.node_combo.clear()
        self.source_tree.blockSignals(True); self.source_tree.clear()
        if not self._nodes:
            self.node_combo.addItem("No executable render nodes found"); self.node_combo.setEnabled(False)
            self.node_combo.blockSignals(False); self.source_tree.blockSignals(False)
            self._selected_paths.clear(); self._update_selection_label(); self.set_node_info(None); return
        self.node_combo.setEnabled(True)
        target_index = 0
        available_paths = [str(node.path) for node in self._nodes]
        if current_path not in available_paths:
            current_path = available_paths[0]
        for index, node in enumerate(self._nodes):
            self.node_combo.addItem(node.display_label)
            if node.path == current_path:
                target_index = index
            item = QtWidgets.QTreeWidgetItem((
                str(node.path), str(node.renderer or "—"), str(node.execution_mode or "—").title(), _frame_text(node), str(node.output_path or "—")
            ))
            item.setData(0, USER_ROLE, str(node.path))
            item.setFlags(ITEM_IS_ENABLED | ITEM_IS_SELECTABLE | ITEM_IS_USER_CHECKABLE)
            should_check = node.path in previous_checked
            if not previous_checked and node.path == current_path:
                should_check = True
            item.setCheckState(0, CHECKED if should_check else UNCHECKED)
            self.source_tree.addTopLevelItem(item)
        self.node_combo.setCurrentIndex(target_index)
        self.node_combo.blockSignals(False); self.source_tree.blockSignals(False)
        self._selected_paths = set(self.selected_node_paths())
        self._pending_selected_paths = []
        self._select_tree_path(current_path)
        self._update_selection_label(); self.set_node_info(self.current_node_info()); self.renderSelectionChanged.emit()

    def _select_tree_path(self, path):
        path = str(path or "")
        for index in range(self.source_tree.topLevelItemCount()):
            item = self.source_tree.topLevelItem(index)
            if str(item.data(0, USER_ROLE) or "") == path:
                self.source_tree.setCurrentItem(item)
                return True
        return False

    def available_node_infos(self):
        return list(self._nodes)

    def current_node_info(self):
        index = self.node_combo.currentIndex()
        return self._nodes[index] if 0 <= index < len(self._nodes) else None

    def current_node_path(self):
        node = self.current_node_info()
        return node.path if node is not None else ""

    def selected_node_paths(self):
        result = []
        for index in range(self.source_tree.topLevelItemCount()):
            item = self.source_tree.topLevelItem(index)
            if item.checkState(0) == CHECKED:
                path = str(item.data(0, USER_ROLE) or "")
                if path and path not in result:
                    result.append(path)
        return result

    def selected_node_infos(self):
        paths = set(self.selected_node_paths())
        return [node for node in self._nodes if str(node.path) in paths]

    def set_selected_node_paths(self, values):
        values = [str(value or "").strip() for value in values or [] if str(value or "").strip()]
        self._pending_selected_paths = list(values)
        if not self._nodes:
            return
        target = set(values)
        self.source_tree.blockSignals(True)
        for index in range(self.source_tree.topLevelItemCount()):
            item = self.source_tree.topLevelItem(index)
            path = str(item.data(0, USER_ROLE) or "")
            item.setCheckState(0, CHECKED if path in target else UNCHECKED)
        self.source_tree.blockSignals(False)
        self._selected_paths = set(self.selected_node_paths()); self._update_selection_label(); self.renderSelectionChanged.emit()

    def select_node_path(self, path):
        path = str(path or "")
        for index, node in enumerate(self._nodes):
            if node.path == path:
                self.node_combo.setCurrentIndex(index); self._select_tree_path(path); return True
        return False

    def _on_source_item_changed(self, item, column):
        if column != 0:
            return
        path = str(item.data(0, USER_ROLE) or "")
        if item.checkState(0) == CHECKED:
            self._selected_paths.add(path)
        else:
            self._selected_paths.discard(path)
        self._update_selection_label(); self.renderSelectionChanged.emit()

    def _on_source_row_changed(self):
        item = self.source_tree.currentItem()
        if item is None:
            return
        path = str(item.data(0, USER_ROLE) or "")
        if path and path != self.current_node_path():
            self.select_node_path(path)

    def _focus_tree_item(self, item, column=0):
        if item is not None:
            self.select_node_path(str(item.data(0, USER_ROLE) or ""))

    def _set_all_checks(self, mode):
        self.source_tree.blockSignals(True)
        try:
            for index in range(self.source_tree.topLevelItemCount()):
                item = self.source_tree.topLevelItem(index)
                node = self._nodes[index] if index < len(self._nodes) else None
                checked = mode == "all" or (mode == "renderable" and node is not None and bool(node.is_renderable) and not bool(node.is_bypassed))
                if mode == "none":
                    checked = False
                item.setCheckState(0, CHECKED if checked else UNCHECKED)
        finally:
            self.source_tree.blockSignals(False)
        self._selected_paths = set(self.selected_node_paths()); self._update_selection_label(); self.renderSelectionChanged.emit()

    def _update_selection_label(self):
        self.selection_label.setText("{} Selected / {} Available".format(len(self.selected_node_paths()), len(self._nodes)))

    @staticmethod
    def _set_combo_values(combo, values, selected=""):
        values = [str(value) for value in values or [] if str(value or "").strip()]
        selected = str(selected or "").strip()
        if selected and selected not in values:
            values.insert(0, selected)
        if not values:
            values = ["Not Set"]
        combo.blockSignals(True); combo.clear(); combo.addItems(values)
        index = combo.findText(selected); combo.setCurrentIndex(index if index >= 0 else 0); combo.blockSignals(False)

    def set_node_info(self, node, prompt=False):
        if node is None:
            if self._context is not None:
                self.start_frame.setValue(self._context.frame_start); self.end_frame.setValue(self._context.frame_end); self.frame_step.setValue(1.0)
            self.node_status.setText("Render-node scanning is manual to keep Houdini stable." if prompt else "No executable render source is focused.")
            self.node_status.set_level("neutral" if prompt else "warning")
            self.renderNodeChanged.emit(None); return
        self._applying_node = True
        try:
            self.start_frame.setValue(node.frame_start); self.end_frame.setValue(node.frame_end); self.frame_step.setValue(node.frame_step)
            self._set_combo_values(self.renderer, node.available_renderers or (node.renderer,), node.renderer or "Not Set")
            self._set_combo_values(self.camera, node.available_cameras or ((node.camera,) if node.camera else ("Not Set",)), node.camera or "Not Set")
            self.execution.setText("Automatic · {}".format(str(node.execution_mode or "hython").title()))
            self.output_source.setCurrentIndex(0)
            self._populate_output_fields(node.output_path, self._context.scene_name if self._context else "houdini_job")
            self.width.setValue(max(0, int(node.resolution_width or 0))); self.height.setValue(max(0, int(node.resolution_height or 0)))
            self.usd_output.setVisible(bool(node.usd_output_path)); self.usd_output.set_value(node.usd_output_path or "Not Set")
            self._set_output_editable(False); self._update_output_preview()
        finally:
            self._applying_node = False
        if not node.details_loaded:
            self.node_status.setText("Loading camera, renderer and output details…"); self.node_status.set_level("info")
        elif node.is_bypassed:
            self.node_status.setText("The focused render source is bypassed."); self.node_status.set_level("error")
        elif not node.output_path:
            self.node_status.setText("Render source detected, but no final image output was found."); self.node_status.set_level("warning")
        else:
            suffix = " · {} source(s) selected".format(len(self.selected_node_paths()))
            self.node_status.setText("Render settings loaded from {}{}.".format(node.path, suffix)); self.node_status.set_level("good")
        self.renderNodeChanged.emit(node)

    def _populate_output_fields(self, output_path, fallback_prefix):
        data = _split_output(output_path, fallback_prefix=fallback_prefix)
        self.output_directory.setText(data["directory"]); self.image_prefix.setText(data["prefix"])
        index = self.file_format.findText(data["format"])
        if index < 0:
            self.file_format.addItem(data["format"]); index = self.file_format.findText(data["format"])
        self.file_format.setCurrentIndex(max(0, index)); self.frame_padding.setValue(data["padding"])

    def replace_current_node(self, node_info):
        index = self.node_combo.currentIndex()
        if node_info is None or not (0 <= index < len(self._nodes)):
            return
        self._nodes[index] = node_info
        if index < self.source_tree.topLevelItemCount():
            item = self.source_tree.topLevelItem(index)
            item.setText(1, str(node_info.renderer or "—")); item.setText(2, str(node_info.execution_mode or "—").title()); item.setText(3, _frame_text(node_info)); item.setText(4, str(node_info.output_path or "—"))
        self.set_node_info(node_info); self.renderSelectionChanged.emit()

    def _set_output_editable(self, editable):
        self.output_directory.setReadOnly(not editable); self.image_prefix.setReadOnly(not editable)
        self.file_format.setEnabled(editable); self.frame_padding.setReadOnly(not editable); self.width.setReadOnly(not editable); self.height.setReadOnly(not editable)

    def _on_output_source_changed(self, index):
        editable = index == 1; self._set_output_editable(editable)
        if not editable:
            node = self.current_node_info()
            if node is not None:
                self._populate_output_fields(node.output_path, self._context.scene_name if self._context else "houdini_job")
                self.width.setValue(max(0, int(node.resolution_width or 0))); self.height.setValue(max(0, int(node.resolution_height or 0)))
        self._update_output_preview()

    def _update_output_preview(self, *args):
        if self.output_source.currentIndex() == 0 and self.current_node_info() is not None:
            path = self.current_node_info().output_path
        else:
            path = _compose_output(self.output_directory.text(), self.image_prefix.text(), self.file_format.currentText(), self.frame_padding.value())
        self.output_preview.set_value(path or "Not Set")

    def _update_override_state(self, *args):
        return

    def submission_values(self):
        node = self.current_node_info()
        camera = self.camera.currentText().strip(); renderer = self.renderer.currentText().strip()
        output_override = self.output_source.currentIndex() == 1
        output_path = _compose_output(self.output_directory.text(), self.image_prefix.text(), self.file_format.currentText(), self.frame_padding.value()) if output_override else (node.output_path if node is not None else "")
        return {
            "frame_start": self.start_frame.value(), "frame_end": self.end_frame.value(), "frame_step": self.frame_step.value(),
            "renderer": renderer, "camera": "" if camera == "Not Set" else camera,
            "execution_mode": node.execution_mode if node is not None else "hython",
            "output_path": str(output_path or "").strip(), "image_prefix": self.image_prefix.text().strip(),
            "file_format": self.file_format.currentText().strip(), "frame_padding": self.frame_padding.value(),
            "width": self.width.value(), "height": self.height.value(),
            "camera_override": bool(node is not None and camera and camera != (node.camera or "Not Set")),
            "renderer_override": bool(node is not None and renderer and renderer != node.renderer),
            "output_override": bool(output_override),
            "resolution_override": bool(output_override and node is not None and (int(self.width.value()) != int(node.resolution_width or 0) or int(self.height.value()) != int(node.resolution_height or 0))),
        }

    def apply_preset(self):
        values = {
            "Preview": (640, 360, "PNG"), "HD": (1280, 720, "PNG"), "Full HD": (1920, 1080, "PNG"),
            "Production EXR": (1920, 1080, "EXR"), "4K Production EXR": (3840, 2160, "EXR"),
        }.get(self.preset_combo.currentText())
        if not values:
            return
        self.output_source.setCurrentIndex(1); self.width.setValue(values[0]); self.height.setValue(values[1])
        index = self.file_format.findText(values[2]); self.file_format.setCurrentIndex(index if index >= 0 else 0)
        if self.frame_padding.value() <= 0:
            self.frame_padding.setValue(4)
        self._update_output_preview()

    def browse_output_directory(self):
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Render Output Directory", self.output_directory.text().strip() or (self._context.output_root if self._context else ""))
        if selected:
            self.output_source.setCurrentIndex(1); self.output_directory.setText(str(selected))

    def state_values(self):
        values = self.submission_values()
        values.update({
            "render_node_path": self.current_node_path(),
            "selected_render_node_paths": self.selected_node_paths(),
            "output_source_index": self.output_source.currentIndex(),
            "preset": self.preset_combo.currentText(),
        })
        return values

    def apply_state(self, data):
        data = dict(data or {})
        selected_paths = data.get("selected_render_node_paths") or []
        if selected_paths:
            self.set_selected_node_paths(selected_paths)
        node_path = str(data.get("render_node_path") or "")
        if node_path:
            self.select_node_path(node_path)
        for widget, key in ((self.start_frame, "frame_start"), (self.end_frame, "frame_end"), (self.frame_step, "frame_step")):
            if key in data:
                widget.setValue(float(data.get(key)))
        if data.get("renderer"):
            index = self.renderer.findText(str(data.get("renderer")))
            if index >= 0:
                self.renderer.setCurrentIndex(index)
        if data.get("camera"):
            index = self.camera.findText(str(data.get("camera")))
            if index >= 0:
                self.camera.setCurrentIndex(index)
        if "output_source_index" in data:
            self.output_source.setCurrentIndex(int(data.get("output_source_index") or 0))
        if data.get("output_path") and self.output_source.currentIndex() == 1:
            self._populate_output_fields(str(data.get("output_path")), self._context.scene_name if self._context else "houdini_job")
        if "width" in data:
            self.width.setValue(int(data.get("width") or 0))
        if "height" in data:
            self.height.setValue(int(data.get("height") or 0))
        if data.get("preset"):
            index = self.preset_combo.findText(str(data.get("preset")))
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
        self._update_output_preview(); self._update_selection_label()

    def _on_node_changed(self, index):
        node = self.current_node_info()
        if node is not None:
            self._select_tree_path(node.path)
        self.set_node_info(node)
