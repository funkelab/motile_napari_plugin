
from motile_plugin.backend.motile_run import MotileRun

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QAbstractItemView
)
from napari.layers import Labels, Layer
from .solver_params import SolverParamsWidget

from warnings import warn
import numpy as np


class RunEditor(QWidget):
    create_run = Signal(MotileRun)
    def __init__(self, run_name, solver_params, layers, multiseg=False):
        # TODO: Don't pass static layers
        super().__init__()
        self.run_name: QLineEdit
        self.layers: list
        self.layer_selection_box: QListWidget
        self.solver_params_widget = SolverParamsWidget(solver_params, editable=True)
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._ui_select_labels_layer(layers, multiseg=multiseg))
        main_layout.addWidget(self.solver_params_widget)
        main_layout.addWidget(self._ui_run_motile(run_name))
        self.setLayout(main_layout)

    def _ui_select_labels_layer(self, layers, multiseg=False) -> QGroupBox:
        # Select Labels layer
        layer_group = QGroupBox("Select Input Layer")
        layer_layout = QHBoxLayout()
        self.layer_selection_box = QListWidget()
        if multiseg:
            self.layer_selection_box.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.update_labels_layers(layers)
        self.layer_selection_box.setToolTip("Select the labels layer you want to use for tracking")
        layer_layout.addWidget(self.layer_selection_box)
        layer_group.setLayout(layer_layout)
        return layer_group

    def update_labels_layers(self, layers):
        self.layers = layers
        self.layer_selection_box.clear()
        for layer in self.layers:
            if isinstance(layer, Labels):
                self.layer_selection_box.addItem(layer.name)
        if len(self.layer_selection_box) > 0:
            self.layer_selection_box.setCurrentRow(0)
        if len(self.layer_selection_box) == 0:
            self.layer_selection_box.addItem("None")

    def get_labels_layer(self) -> list[Layer]:
        layer_names = [i.text() for i in self.layer_selection_box.selectedItems()]
        if len(layer_names) == 1 and layer_names[0] == "None":
            return None
        return [self.layers[name] for name in layer_names]

    def _ui_run_motile(self, run_name) -> QGroupBox:
        # Specify name text box
        run_group = QGroupBox("Run")
        run_layout = QVBoxLayout()
        run_name_layout = QFormLayout()
        self.run_name = QLineEdit(run_name)
        run_name_layout.addRow("Run Name:", self.run_name)
        run_layout.addLayout(run_name_layout)

        print_params_btn = QPushButton("Print Params")
        print_params_btn.clicked.connect(self._print_parameters)
        run_layout.addWidget(print_params_btn)

        # Generate Tracks button
        generate_tracks_btn = QPushButton("Create Run")
        generate_tracks_btn.clicked.connect(self.emit_run)
        generate_tracks_btn.setToolTip("Run tracking. Might take minutes or longer for larger samples.")
        run_layout.addWidget(generate_tracks_btn)

        # Add running widget
        self.running_label = QLabel("Solver is running")
        self.running_label.hide()
        run_layout.addWidget(self.running_label)
        run_group.setLayout(run_layout)
        return run_group

    def get_run_name(self):
        return self.run_name.text()

    def get_run(self):
        run_name = self.get_run_name()
        input_layers = self.get_labels_layer()
        if input_layers is None or len(input_layers) == 0:
            warn("No input labels layer selected")
            return None
        if len(input_layers) == 1:
            input_segs = np.expand_dims(input_layers[0].data, 1)
        else:
            input_segs = np.stack([labels.data for labels in input_layers], axis=1)
        print(f"{input_segs.shape=}")
        params = self.solver_params_widget.solver_params
        return MotileRun(run_name=run_name, solver_params=params, input_segmentation=input_segs)
    
    def emit_run(self):
        run = self.get_run()
        if run is not None:
            self.create_run.emit(run)
    
    def new_run(self, run):
        self.run_name.setText(run.run_name)
        self.solver_params_widget.new_params.emit(run.solver_params)

    def _print_parameters(self):
        print(f"Solving with parameters {self.solver_params_widget.solver_params}")