from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from warnings import warn

import napari.layers
import numpy as np
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

from motile_plugin.backend.motile_run import MotileRun

from .params_editor import SolverParamsEditor

if TYPE_CHECKING:
    import napari

logger = logging.getLogger(__name__)


class RunEditor(QGroupBox):
    start_run = Signal(MotileRun)

    def __init__(self, viewer: napari.Viewer):
        """A widget for editing run parameters and starting solving.
        Has to know about the viewer to get the input segmentation
        from the current layers.

        Args:
            viewer (napari.Viewer): The napari viewer that the editor should
                get the input segmentation from.
        """
        super().__init__(title="Run Editor")
        self.viewer = viewer
        self.solver_params_widget = SolverParamsEditor()
        self.run_name: QLineEdit
        self.layer_selection_box: QComboBox

        # Generate Tracks button
        generate_tracks_btn = QPushButton("Run Tracking")
        generate_tracks_btn.clicked.connect(self.emit_run)
        generate_tracks_btn.setToolTip(
            "Might take minutes or longer for larger samples."
        )

        main_layout = QVBoxLayout()
        main_layout.addWidget(self._run_widget())
        main_layout.addWidget(self._labels_layer_widget())
        main_layout.addWidget(self.solver_params_widget)
        main_layout.addWidget(generate_tracks_btn)
        self.setLayout(main_layout)

    def update_labels_layers(self) -> None:
        """Update the layer selection box with the input layers in the viewer"""
        prev_selection = self.layer_selection_box.currentText()
        self.layer_selection_box.clear()
        for layer in self.viewer.layers:
            if isinstance(layer, (napari.layers.Labels, napari.layers.Points)):
                self.layer_selection_box.addItem(layer.name)
        self.layer_selection_box.setCurrentText(prev_selection)

    def update_layer_selection(self) -> None:
        """Update the rest of the UI when the selected layer is updated"""
        layer = self.get_input_layer()
        if layer is None:
            return
        if isinstance(layer, napari.layers.Labels):
            enable_iou = True
        elif isinstance(layer, napari.layers.Points):
            enable_iou = False
        self.solver_params_widget.iou_row.toggle_visible(enable_iou)

    def _labels_layer_widget(self) -> QWidget:
        """Create the widget to select the input layer. Uses magicgui,
        but explicitly connects to the viewer layers events to keep it synced.

        Returns:
            QWidget: A dropdown select with all the labels layers in layers
                and a refresh button to sync with napari.
        """
        layer_group = QWidget()
        layer_layout = QHBoxLayout()
        layer_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("Input Layer:")
        layer_layout.addWidget(label)
        label.setToolTip(
            "Select the labels layer you want to use for tracking"
        )

        # # Layer selection combo box
        self.layer_selection_box = QComboBox()
        self.update_labels_layers()
        layers_events = self.viewer.layers.events
        layers_events.inserted.connect(self.update_labels_layers)
        layers_events.removed.connect(self.update_labels_layers)
        layers_events.reordered.connect(self.update_labels_layers)
        self.layer_selection_box.currentTextChanged.connect(
            self.update_layer_selection
        )

        size_policy = self.layer_selection_box.sizePolicy()
        size_policy.setHorizontalPolicy(QSizePolicy.MinimumExpanding)
        self.layer_selection_box.setSizePolicy(size_policy)
        layer_layout.addWidget(self.layer_selection_box)

        layer_group.setLayout(layer_layout)
        return layer_group

    def get_input_layer(self) -> napari.layers.Layer | None:
        """Get the input segmentation or points in current selection in the
        layer dropdown.

        Returns:
            napari.layers.Layer | None: The points or labels layer with the name
                that is selected, or None if no layer is selected.
        """
        layer_name = self.layer_selection_box.currentText()
        if layer_name is None or layer_name not in self.viewer.layers:
            return None
        return self.viewer.layers[layer_name]

    def reshape_labels(self, segmentation: np.ndarray) -> np.ndarray:
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

    def _run_widget(self) -> QWidget:
        """Construct a widget where you set the run name and start solving.
        Initializes self.run_name and connects the generate tracks button
        to emit the new_run signal.

        Returns:
            QWidget: A row widget with a line edit for run name and a button
                to create a new run and start solving.
        """
        # Specify name text box
        run_widget = QWidget()
        run_layout = QHBoxLayout()
        run_layout.setContentsMargins(0, 0, 0, 0)
        run_layout.addWidget(QLabel("Run Name:"))
        self.run_name = QLineEdit("new_run")
        run_layout.addWidget(self.run_name)

        run_widget.setLayout(run_layout)
        return run_widget

    def get_run(self) -> MotileRun | None:
        """Construct a motile run from the current state of the run editor
        widget.

        Returns:
            MotileRun: A run with name, parameters, and input segmentation.
                Output segmentation and tracks not yet specified.
        """
        run_name = self.run_name.text()
        input_layer = self.get_input_layer()
        if input_layer is None:
            warn("No input layer selected", stacklevel=2)
            return None
        if isinstance(input_layer, napari.layers.Labels):
            input_seg = self.reshape_labels(input_layer.data)
            input_points = None
        elif isinstance(input_layer, napari.layers.Points):
            input_seg = None
            input_points = input_layer.data
        params = self.solver_params_widget.solver_params.copy()
        return MotileRun(
            run_name=run_name,
            solver_params=params,
            input_segmentation=input_seg,
            input_points=input_points,
            time=datetime.now(),
            scale=input_layer.scale,
        )

    def emit_run(self) -> None:
        """Construct a run and start solving by emitting the start run
        signal for the main widget to connect to. If run is invalid, will
        not emit the signal.
        """
        run = self.get_run()
        if run is not None:
            self.start_run.emit(run)

    def new_run(self, run: MotileRun) -> None:
        """Configure the run editor to copy the name and params of the given
        run.
        """
        self.run_name.setText(run.run_name)
        self.solver_params_widget.new_params.emit(run.solver_params)
