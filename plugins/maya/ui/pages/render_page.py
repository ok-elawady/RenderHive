from __future__ import print_function

from ..qt_compat import QtWidgets
from ..common_widgets import Card, LabeledField
from ..targeting_widgets import RenderLayerSelector

def build_render_page(self, register):
    page, body = self.scroll_page(
        "Render Configuration",
        "Configure frame range, Arnold camera, format and output resolution.",
    )

    preset_card = Card("Render Preset", "Apply a tested baseline, then adjust individual render settings as needed.")
    preset_row = QtWidgets.QHBoxLayout()

    preset = register("render_preset", QtWidgets.QComboBox())
    preset.addItems(
        [
            "Manual Configuration",
            "Preview",
            "HD",
            "Full HD",
            "Production EXR",
        ]
    )

    apply_button = QtWidgets.QPushButton("Apply Preset")
    apply_button.setObjectName("PrimaryButton")
    apply_button.clicked.connect(self.apply_preset)

    preset_row.addWidget(preset, 1)
    preset_row.addWidget(apply_button)
    preset_card.layout.addLayout(preset_row)
    body.addWidget(preset_card)

    layers_card = Card(
        "Render Layers",
        "Choose one or more Maya Render Setup layers. Shared render settings below apply to every selected layer.",
    )
    layer_selector = register("rh_render_layers", RenderLayerSelector())
    layer_selector.selectionChanged.connect(self.on_render_layer_selection_changed)
    layer_selector.refreshRequested.connect(self.refresh_render_layers)
    layers_card.layout.addWidget(layer_selector)
    body.addWidget(layers_card)

    render_card = Card("Frame Range & Arnold", "RenderHive Maya renders with Arnold. Choose the shared frames and camera used by the selected layers.")
    render_grid = QtWidgets.QGridLayout()
    render_grid.setHorizontalSpacing(10)
    render_grid.setVerticalSpacing(8)

    frame_start = register("rh_frame_start", QtWidgets.QSpinBox())
    frame_end = register("rh_frame_end", QtWidgets.QSpinBox())
    frame_step = register("rh_frame_step", QtWidgets.QSpinBox())
    for widget in (frame_start, frame_end):
        widget.setRange(-1000000, 1000000)
    frame_step.setRange(1, 1000)
    frame_step.setValue(1)

    renderer = register("rh_renderer", QtWidgets.QComboBox())
    renderer.addItem("arnold")
    renderer.setToolTip("RenderHive Maya currently supports Arnold only.")

    camera = register("rh_camera", QtWidgets.QComboBox())
    camera.addItem("Loading")

    render_grid.addWidget(LabeledField("Start Frame", frame_start, "First frame included in the submission."), 0, 0)
    render_grid.addWidget(LabeledField("End Frame", frame_end, "Last frame included in the submission."), 0, 1)
    render_grid.addWidget(LabeledField("Frame Step", frame_step, "Increment between submitted frames."), 1, 0)
    render_grid.addWidget(LabeledField("Renderer", renderer, "RenderHive Maya currently submits Arnold renders only."), 1, 1)
    render_grid.addWidget(LabeledField("Render Camera", camera, "Camera used for this render submission."), 2, 0, 1, 2)
    render_grid.setColumnStretch(0, 1)
    render_grid.setColumnStretch(1, 1)
    render_card.layout.addLayout(render_grid)
    body.addWidget(render_card)

    output_card = Card("Output Settings", "Define the output prefix, file format, frame padding and resolution.")
    output_grid = QtWidgets.QGridLayout()
    output_grid.setHorizontalSpacing(10)
    output_grid.setVerticalSpacing(8)

    image_name = register("rh_image_name", QtWidgets.QLineEdit())
    image_name.setPlaceholderText("Enter the output file prefix")

    image_format = register("rh_image_format", QtWidgets.QComboBox())
    image_format.addItems(["png", "jpg", "exr", "tif"])

    padding = register("rh_frame_padding", QtWidgets.QSpinBox())
    padding.setRange(1, 12)
    padding.setValue(4)

    width = register("rh_width", QtWidgets.QSpinBox())
    height = register("rh_height", QtWidgets.QSpinBox())
    for widget in (width, height):
        widget.setRange(1, 65536)

    output_grid.addWidget(LabeledField("Image Prefix", image_name, "Base name written before the frame number and file extension."), 0, 0, 1, 2)
    output_grid.addWidget(LabeledField("File Format", image_format, "Image file format written by the renderer."), 1, 0)
    output_grid.addWidget(LabeledField("Frame Padding", padding, "Number of digits used for frame numbers in output filenames."), 1, 1)
    output_grid.addWidget(LabeledField("Width", width, "Output image width in pixels."), 2, 0)
    output_grid.addWidget(LabeledField("Height", height, "Output image height in pixels."), 2, 1)
    output_grid.setColumnStretch(0, 1)
    output_grid.setColumnStretch(1, 1)
    output_card.layout.addLayout(output_grid)
    body.addWidget(output_card)

    body.addStretch()
    return page

