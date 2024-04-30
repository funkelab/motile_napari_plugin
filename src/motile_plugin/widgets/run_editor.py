from __future__ import annotations
from typing import TYPE_CHECKING
from warnings import warn
import logging

import numpy as np
from motile_plugin.backend.motile_run import MotileRun
from napari.layers import Labels, Layer
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .solver_params import SolverParamsWidget

if TYPE_CHECKING:
    from motile_plugin.backend.solver_params import SolverParams
    from napari.layers import Layer

logger = logging.getLogger(__name__)


class RunEditor(QWidget):
    create_run = Signal(MotileRun)

    def __init__(self, run_name: str, solver_params: SolverParams, layers: list[Layer]):
        super().__init__()
        self.run_name: QLineEdit
        self.layers: list
        self.layer_selection_box: QComboBox
        self.solver_params_widget = SolverParamsWidget(
            solver_params, editable=True
        )
        main_layout = QVBoxLayout()
        main_layout.addWidget(
            self._ui_select_labels_layer(layers)
        )
        main_layout.addWidget(self.solver_params_widget)
        main_layout.addWidget(self._ui_run_motile(run_name))
        self.setLayout(main_layout)

    def _ui_select_labels_layer(self, layers: list[Layer]) -> QGroupBox:
        layer_group = QGroupBox("Select Input Layer")
        layer_layout = QHBoxLayout()
        self.layer_selection_box = QComboBox()
        self.update_labels_layers(layers)
        self.layer_selection_box.setToolTip(
            "Select the labels layer you want to use for tracking"
        )
        layer_layout.addWidget(self.layer_selection_box)
        layer_group.setLayout(layer_layout)
        return layer_group

    def update_labels_layers(self, layers: list[Layer]) -> None:
        self.layers = layers
        self.layer_selection_box.clear()
        for layer in self.layers:
            if isinstance(layer, Labels):
                self.layer_selection_box.addItem(layer.name)
        if len(self.layer_selection_box) == 0:
            self.layer_selection_box.addItem("None")

    def get_labels_layer(self) -> Layer:
        layer_name = self.layer_selection_box.currentText()
        if layer_name == "None":
            return None
        return self.layers[layer_name]

    def reshape_labels(self, segmentation: np.ndarray) -> None:
        """Expect napari segmentation to have shape t, [z], y, x.
        Motile toolbox needs a channel dimension between time and space.
        This also raises an error if the input seg is not the expected shape.

        Args:
            segmentation (np.ndarray): _description_

        Raises:
            ValueError if segmentation is not 3D or 4D.
        """
        ndim = segmentation.ndim
        if ndim > 4:
            raise ValueError(
                "Expected segmentation to be at most 4D, found %d",
                ndim
            )
        elif ndim < 3:
            raise ValueError(
                "Expected segmentation to be at least 3D, found %d",
                ndim
            )
        reshaped = np.expand_dims(segmentation, 1)
        return reshaped

    def _ui_run_motile(self, run_name: str) -> QGroupBox:
        # Specify name text box
        run_group = QGroupBox("Run")
        run_layout = QVBoxLayout()
        run_name_layout = QFormLayout()
        self.run_name = QLineEdit(run_name)
        run_name_layout.addRow("Run Name:", self.run_name)
        run_layout.addLayout(run_name_layout)

        # Generate Tracks button
        generate_tracks_btn = QPushButton("Create Run")
        generate_tracks_btn.clicked.connect(self.emit_run)
        generate_tracks_btn.setToolTip(
            "Run tracking. Might take minutes or longer for larger samples."
        )
        run_layout.addWidget(generate_tracks_btn)

        # Add running widget
        self.running_label = QLabel("Solver is running")
        self.running_label.hide()
        run_layout.addWidget(self.running_label)
        run_group.setLayout(run_layout)
        return run_group

    def get_run_name(self) -> str:
        return self.run_name.text()

    def get_run(self) -> MotileRun:
        run_name = self.get_run_name()
        input_layer = self.get_labels_layer()
        if input_layer is None:
            warn("No input labels layer selected", stacklevel=2)
            return None
        input_seg = self.reshape_labels(input_layer.data)
        params = self.solver_params_widget.solver_params.copy()
        return MotileRun(
            run_name=run_name,
            solver_params=params,
            input_segmentation=input_seg,
        )

    def emit_run(self) -> None:
        run = self.get_run()
        if run is not None:
            self.create_run.emit(run)

    def new_run(self, run) -> None:
        self.run_name.setText(run.run_name)
        self.solver_params_widget.new_params.emit(run.solver_params)
