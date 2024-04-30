from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from warnings import warn

import numpy as np
from fonticon_fa6 import FA6S
from motile_plugin.backend.motile_run import MotileRun
from napari.layers import Labels
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon

from .solver_params import SolverParamsWidget

if TYPE_CHECKING:
    from motile_plugin.backend.solver_params import SolverParams
    from napari.layers import Layer

logger = logging.getLogger(__name__)


class RunEditor(QGroupBox):
    create_run = Signal(MotileRun)

    def __init__(
        self, run_name: str, solver_params: SolverParams, layers: list[Layer]
    ):
        super().__init__(title="Run Editor")
        self.run_name: QLineEdit
        self.layers: list
        self.refresh_layer_button: QPushButton
        self.layer_selection_box: QComboBox
        self.solver_params_widget = SolverParamsWidget(
            solver_params, editable=True
        )
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._run_widget(run_name))
        main_layout.addWidget(self._labels_layer_widget(layers))
        main_layout.addWidget(self.solver_params_widget)
        self.setLayout(main_layout)

    def _labels_layer_widget(self, layers: list[Layer]) -> QWidget:
        """Create the widget to select the input layer. It is difficult
        to keep the list in sync with the napari layers, so there is an
        explicit refresh button to sync them.

        Args:
            layers (list[Layer]): The current set of layers in napari

        Returns:
            QWidget: A dropdown select with all the labels layers in layers
                and a refresh button to sync with napari (must be connected
                in main widget)
        """
        layer_group = QWidget()
        layer_layout = QHBoxLayout()
        layer_layout.setContentsMargins(0, 0, 0, 0)
        layer_layout.addWidget(QLabel("Input Layer:"))

        # Layer selection combo box
        self.layer_selection_box = QComboBox()
        self.update_labels_layers(layers)
        self.layer_selection_box.setToolTip(
            "Select the labels layer you want to use for tracking"
        )
        size_policy = self.layer_selection_box.sizePolicy()
        size_policy.setHorizontalPolicy(QSizePolicy.MinimumExpanding)
        self.layer_selection_box.setSizePolicy(size_policy)
        layer_layout.addWidget(self.layer_selection_box)

        # Refresh button
        self.refresh_layer_button = QPushButton(
            icon=icon(FA6S.arrows_rotate, color="white")
        )
        self.refresh_layer_button.setToolTip(
            "Refresh this selection box with current napari layers"
        )
        layer_layout.addWidget(self.refresh_layer_button)

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
                "Expected segmentation to be at most 4D, found %d", ndim
            )
        elif ndim < 3:
            raise ValueError(
                "Expected segmentation to be at least 3D, found %d", ndim
            )
        reshaped = np.expand_dims(segmentation, 1)
        return reshaped

    def _run_widget(self, run_name: str) -> QWidget:
        # Specify name text box
        run_widget = QWidget()
        run_layout = QHBoxLayout()
        run_layout.setContentsMargins(0, 0, 0, 0)
        run_layout.addWidget(QLabel("Run Name:"))
        self.run_name = QLineEdit(run_name)
        run_layout.addWidget(self.run_name)

        # Generate Tracks button
        generate_tracks_btn = QPushButton("Go!")
        generate_tracks_btn.clicked.connect(self.emit_run)
        generate_tracks_btn.setToolTip(
            "Run tracking. Might take minutes or longer for larger samples."
        )
        run_layout.addWidget(generate_tracks_btn)
        run_widget.setLayout(run_layout)
        return run_widget

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
