"""Render source, camera, renderer and output settings."""

from __future__ import absolute_import

import os
import re

from renderhive_houdini.ui.qt_compat import QtWidgets, Signal
from renderhive_houdini.ui.widgets import (
    PageHeader,
    SectionCard,
    LabeledField,
    ReadOnlyRow,
    InlineStatus,
)


_FORMATS = ("EXR", "PNG", "JPG", "TIFF", "TGA", "BMP", "RAT")


def _output_format(path):
    value = str(path or "")
    extension = os.path.splitext(value)[1].lower().lstrip(".")
    return extension.upper() if extension else "EXR"


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
    return bool(
        re.search(r"\$F\d*", value, re.IGNORECASE)
        or re.search(r"%0?\d*d", value)
        or "#" in value
    )


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


class RenderPage(QtWidgets.QWidget):
    refreshRequested = Signal()
    useSelectedRequested = Signal()
    renderNodeChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes = []
        self._context = None
        self._scene_key = ""
        self._applying_node = False
        self._node_output_path = ""

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        root.addWidget(PageHeader(
            "Render Configuration",
            "Select a render source, camera and output settings for this job.",
        ))

        source = SectionCard("Render Source", "Select an executable ROP or Solaris render node.")
        selector = QtWidgets.QHBoxLayout()
        selector.setSpacing(8)
        self.node_combo = QtWidgets.QComboBox()
        self.node_combo.setMinimumWidth(340)
        self.node_combo.currentIndexChanged.connect(self._on_node_changed)
        self.refresh_button = QtWidgets.QPushButton("Refresh Nodes")
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.selected_button = QtWidgets.QPushButton("Use Selected Node")
        self.selected_button.setObjectName("PrimaryButton")
        self.selected_button.clicked.connect(self.useSelectedRequested.emit)
        selector.addWidget(self.node_combo, 1)
        selector.addWidget(self.refresh_button)
        selector.addWidget(self.selected_button)
        source.layout.addLayout(selector)
        self.node_status = InlineStatus("Open a scene, then refresh or use the selected render node.", "neutral")
        source.layout.addWidget(self.node_status)

        frames = SectionCard("Frame Range & Renderer", "Frame range is editable. Renderer, camera and execution mode are derived from the selected source.")
        frame_grid = QtWidgets.QGridLayout()
        frame_grid.setHorizontalSpacing(10)
        frame_grid.setVerticalSpacing(8)
        self.start_frame = QtWidgets.QDoubleSpinBox()
        self.start_frame.setRange(-1000000, 1000000)
        self.start_frame.setDecimals(3)
        self.end_frame = QtWidgets.QDoubleSpinBox()
        self.end_frame.setRange(-1000000, 1000000)
        self.end_frame.setDecimals(3)
        self.frame_step = QtWidgets.QDoubleSpinBox()
        self.frame_step.setRange(0.001, 100000)
        self.frame_step.setDecimals(3)
        self.frame_step.setValue(1)
        self.renderer = QtWidgets.QComboBox()
        self.renderer.currentIndexChanged.connect(self._update_override_state)
        self.camera = QtWidgets.QComboBox()
        self.camera.currentIndexChanged.connect(self._update_override_state)
        self.execution = QtWidgets.QLineEdit()
        self.execution.setReadOnly(True)

        frame_grid.addWidget(LabeledField("Start Frame", self.start_frame, "First frame submitted to the farm."), 0, 0)
        frame_grid.addWidget(LabeledField("End Frame", self.end_frame, "Last frame submitted to the farm."), 0, 1)
        frame_grid.addWidget(LabeledField("Frame Step", self.frame_step, "Increment between submitted frames."), 1, 0)
        frame_grid.addWidget(LabeledField("Renderer", self.renderer, "Compatible renderers detected from the selected render source."), 1, 1)
        frame_grid.addWidget(LabeledField("Render Camera", self.camera, "Cameras detected from /obj or the active Solaris stage."), 2, 0)
        frame_grid.addWidget(LabeledField("Execution Mode", self.execution, "Automatically uses Hython for ROP jobs and Husk for USD/Solaris jobs."), 2, 1)
        frame_grid.setColumnStretch(0, 1)
        frame_grid.setColumnStretch(1, 1)
        frames.layout.addLayout(frame_grid)

        output = SectionCard("Output Settings", "Use the render source values or override them for this farm submission only.")
        output_grid = QtWidgets.QGridLayout()
        output_grid.setHorizontalSpacing(10)
        output_grid.setVerticalSpacing(8)

        self.output_source = QtWidgets.QComboBox()
        self.output_source.addItems((
            "Use Render Node Settings",
            "Override for This Job",
        ))
        self.output_source.currentIndexChanged.connect(self._on_output_source_changed)
        output_grid.addWidget(LabeledField(
            "Output Source",
            self.output_source,
            "Overrides are sent to the Worker and do not modify the saved HIP file.",
        ), 0, 0, 1, 2)

        self.output_directory = QtWidgets.QLineEdit()
        self.output_directory.textChanged.connect(self._update_output_preview)
        self.image_prefix = QtWidgets.QLineEdit()
        self.image_prefix.textChanged.connect(self._update_output_preview)
        self.file_format = QtWidgets.QComboBox()
        self.file_format.addItems(_FORMATS)
        self.file_format.currentIndexChanged.connect(self._update_output_preview)
        self.frame_padding = QtWidgets.QSpinBox()
        self.frame_padding.setRange(0, 20)
        self.frame_padding.valueChanged.connect(self._update_output_preview)
        self.width = QtWidgets.QSpinBox()
        self.width.setRange(0, 100000)
        self.height = QtWidgets.QSpinBox()
        self.height.setRange(0, 100000)

        output_grid.addWidget(LabeledField("Output Directory", self.output_directory, "Directory for final rendered images, not the intermediate USD file."), 1, 0, 1, 2)
        output_grid.addWidget(LabeledField("Image Prefix", self.image_prefix, "Base filename before the frame token and extension."), 2, 0)
        output_grid.addWidget(LabeledField("File Format", self.file_format), 2, 1)
        output_grid.addWidget(LabeledField("Frame Padding", self.frame_padding), 3, 0)
        resolution = QtWidgets.QWidget()
        resolution_layout = QtWidgets.QHBoxLayout(resolution)
        resolution_layout.setContentsMargins(0, 0, 0, 0)
        resolution_layout.setSpacing(8)
        resolution_layout.addWidget(self.width)
        resolution_layout.addWidget(self.height)
        output_grid.addWidget(LabeledField("Resolution", resolution, "Width and height used by the Worker."), 3, 1)
        output_grid.setColumnStretch(0, 1)
        output_grid.setColumnStretch(1, 1)
        output.layout.addLayout(output_grid)

        self.output_preview = ReadOnlyRow(
            "Final Image Output",
            tooltip="The final image path submitted to RenderHive.",
        )
        output.layout.addWidget(self.output_preview)
        self.usd_output = ReadOnlyRow(
            "Intermediate USD",
            tooltip="USD file generated by a Solaris USD Render ROP. This is not the final rendered image.",
        )
        self.usd_output.setVisible(False)
        output.layout.addWidget(self.usd_output)

        root.addWidget(source)
        root.addWidget(frames)
        root.addWidget(output)
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
        self.node_combo.blockSignals(True)
        self.node_combo.clear()
        self.node_combo.addItem("Refresh Nodes or use the selected node")
        self.node_combo.setEnabled(False)
        self.node_combo.blockSignals(False)
        self.set_node_info(None, prompt=True)

    def set_context(self, context, reset_scene=False):
        new_key = self._context_key(context)
        scene_changed = bool(reset_scene or (self._scene_key and new_key != self._scene_key))
        self._scene_key = new_key
        self._context = context

        if scene_changed:
            self._nodes = []
            self.node_combo.blockSignals(True)
            self.node_combo.clear()
            self.node_combo.blockSignals(False)

        if self.current_node_info() is None:
            self.start_frame.setValue(context.frame_start)
            self.end_frame.setValue(context.frame_end)
            self.frame_step.setValue(1.0)
            self._set_combo_values(self.renderer, ("Select a render node",), "Select a render node")
            self._set_combo_values(self.camera, ("Not Set",), "Not Set")
            self.execution.setText("Automatic")
            default_path = os.path.join(
                context.output_root or context.hip_directory or "",
                "{}.$F4.exr".format(context.scene_name or "houdini_job"),
            )
            self._node_output_path = default_path
            self._populate_output_fields(default_path, context.scene_name or "houdini_job")
            self.width.setValue(0)
            self.height.setValue(0)
            self.usd_output.setVisible(False)
            self._update_output_preview()
        return scene_changed

    def set_nodes(self, nodes, preferred_path=""):
        current_path = preferred_path or self.current_node_path()
        self._nodes = list(nodes or [])
        self.node_combo.blockSignals(True)
        self.node_combo.clear()
        if not self._nodes:
            self.node_combo.addItem("No executable render nodes found")
            self.node_combo.setEnabled(False)
            self.node_combo.blockSignals(False)
            self.set_node_info(None)
            return
        self.node_combo.setEnabled(True)
        target_index = 0
        for index, node in enumerate(self._nodes):
            self.node_combo.addItem(node.display_label)
            if node.path == current_path:
                target_index = index
        self.node_combo.setCurrentIndex(target_index)
        self.node_combo.blockSignals(False)
        self.set_node_info(self.current_node_info())

    def current_node_info(self):
        index = self.node_combo.currentIndex()
        return self._nodes[index] if 0 <= index < len(self._nodes) else None

    def current_node_path(self):
        node = self.current_node_info()
        return node.path if node is not None else ""

    def select_node_path(self, path):
        for index, node in enumerate(self._nodes):
            if node.path == path:
                self.node_combo.setCurrentIndex(index)
                return True
        return False

    @staticmethod
    def _set_combo_values(combo, values, selected=""):
        values = [str(value) for value in values or [] if str(value or "").strip()]
        selected = str(selected or "").strip()
        if selected and selected not in values:
            values.insert(0, selected)
        if not values:
            values = ["Not Set"]
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(values)
        index = combo.findText(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def set_node_info(self, node, prompt=False):
        if node is None:
            if self._context is not None:
                self.set_context(self._context)
            self.node_status.setText(
                "Render-node scanning is manual to keep Houdini stable."
                if prompt else "No executable render node is selected."
            )
            self.node_status.set_level("neutral" if prompt else "warning")
            self.renderNodeChanged.emit(None)
            return

        self._applying_node = True
        try:
            self.start_frame.setValue(node.frame_start)
            self.end_frame.setValue(node.frame_end)
            self.frame_step.setValue(node.frame_step)
            self._set_combo_values(
                self.renderer,
                node.available_renderers or (node.renderer,),
                node.renderer or "Not Set",
            )
            self._set_combo_values(
                self.camera,
                node.available_cameras or ((node.camera,) if node.camera else ("Not Set",)),
                node.camera or "Not Set",
            )
            self.execution.setText(
                "Automatic · {}".format(str(node.execution_mode or "hython").title())
            )
            self._node_output_path = str(node.output_path or "")
            self.output_source.setCurrentIndex(0)
            self._populate_output_fields(
                node.output_path,
                self._context.scene_name if self._context else "houdini_job",
            )
            self.width.setValue(max(0, int(node.resolution_width or 0)))
            self.height.setValue(max(0, int(node.resolution_height or 0)))
            self.usd_output.setVisible(bool(node.usd_output_path))
            self.usd_output.set_value(node.usd_output_path or "Not Set")
            self._set_output_editable(False)
            self._update_output_preview()
        finally:
            self._applying_node = False

        if not node.details_loaded:
            self.node_status.setText("Loading camera, renderer and final output details…")
            self.node_status.set_level("info")
        elif node.is_bypassed:
            self.node_status.setText("The selected render node is bypassed.")
            self.node_status.set_level("error")
        elif not node.output_path:
            self.node_status.setText("Render source detected, but no final image output was found.")
            self.node_status.set_level("warning")
        else:
            self.node_status.setText("Render settings loaded from {}.".format(node.path))
            self.node_status.set_level("good")
        self.renderNodeChanged.emit(node)

    def _populate_output_fields(self, output_path, fallback_prefix):
        data = _split_output(output_path, fallback_prefix=fallback_prefix)
        self.output_directory.setText(data["directory"])
        self.image_prefix.setText(data["prefix"])
        index = self.file_format.findText(data["format"])
        if index < 0:
            self.file_format.addItem(data["format"])
            index = self.file_format.findText(data["format"])
        self.file_format.setCurrentIndex(max(0, index))
        self.frame_padding.setValue(data["padding"])

    def replace_current_node(self, node_info):
        index = self.node_combo.currentIndex()
        if node_info is None or not (0 <= index < len(self._nodes)):
            return
        self._nodes[index] = node_info
        self.set_node_info(node_info)

    def _set_output_editable(self, editable):
        self.output_directory.setReadOnly(not editable)
        self.image_prefix.setReadOnly(not editable)
        self.file_format.setEnabled(editable)
        self.frame_padding.setReadOnly(not editable)
        self.width.setReadOnly(not editable)
        self.height.setReadOnly(not editable)

    def _on_output_source_changed(self, index):
        editable = index == 1
        self._set_output_editable(editable)
        if not editable:
            node = self.current_node_info()
            if node is not None:
                self._populate_output_fields(
                    node.output_path,
                    self._context.scene_name if self._context else "houdini_job",
                )
                self.width.setValue(max(0, int(node.resolution_width or 0)))
                self.height.setValue(max(0, int(node.resolution_height or 0)))
        self._update_output_preview()

    def _update_output_preview(self, *args):
        if self.output_source.currentIndex() == 0 and self.current_node_info() is not None:
            path = self.current_node_info().output_path
        else:
            path = _compose_output(
                self.output_directory.text(),
                self.image_prefix.text(),
                self.file_format.currentText(),
                self.frame_padding.value(),
            )
        self.output_preview.set_value(path or "Not Set")

    def _update_override_state(self, *args):
        if self._applying_node:
            return

    def submission_values(self):
        node = self.current_node_info()
        camera = self.camera.currentText().strip()
        renderer = self.renderer.currentText().strip()
        output_override = self.output_source.currentIndex() == 1
        output_path = (
            _compose_output(
                self.output_directory.text(),
                self.image_prefix.text(),
                self.file_format.currentText(),
                self.frame_padding.value(),
            )
            if output_override
            else (node.output_path if node is not None else self.output_preview.value_label.text())
        )
        return {
            "frame_start": self.start_frame.value(),
            "frame_end": self.end_frame.value(),
            "frame_step": self.frame_step.value(),
            "renderer": renderer,
            "camera": "" if camera == "Not Set" else camera,
            "execution_mode": node.execution_mode if node is not None else "hython",
            "output_path": str(output_path or "").strip(),
            "image_prefix": self.image_prefix.text().strip(),
            "file_format": self.file_format.currentText().strip(),
            "frame_padding": self.frame_padding.value(),
            "width": self.width.value(),
            "height": self.height.value(),
            "camera_override": bool(node is not None and camera and camera != (node.camera or "Not Set")),
            "renderer_override": bool(node is not None and renderer and renderer != node.renderer),
            "output_override": bool(output_override),
            "resolution_override": bool(
                output_override
                and node is not None
                and (
                    int(self.width.value()) != int(node.resolution_width or 0)
                    or int(self.height.value()) != int(node.resolution_height or 0)
                )
            ),
        }

    def _on_node_changed(self, index):
        self.set_node_info(self.current_node_info())
