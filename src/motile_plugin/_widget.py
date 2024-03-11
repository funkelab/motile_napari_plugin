from typing import TYPE_CHECKING

from magicgui import magic_factory
from magicgui.widgets import CheckBox, Container, create_widget
from qtpy.QtWidgets import (
    QWidget, QPushButton, QSlider, QHBoxLayout, QVBoxLayout, 
    QLabel, QSpinBox, QCheckBox, QDoubleSpinBox, QGroupBox, QLineEdit,
    QComboBox, QFormLayout
)
from qtpy.QtCore import Qt
from skimage.util import img_as_float
#from napari_graph import UndirectedGraph
import numpy as np
from napari.layers import Labels
import pandas as pd

if TYPE_CHECKING:
    import napari


import math
from pathlib import Path
import numpy as np

from motile import Solver, TrackGraph
from motile.constraints import MaxChildren, MaxParents
from motile.costs import EdgeSelection, Appear
from motile.variables import NodeSelected, EdgeSelected
import networkx as nx
import toml
from tqdm import tqdm
import pprint
import time
from skimage.measure import regionprops
import tifffile
import logging

from motile_toolbox.candidate_graph import graph_from_segmentation
from motile_toolbox.visualization import to_napari_tracks_layer
from ._utils import (
    solve_with_motile, get_solution_nx_graph)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)-8s %(message)s"
)
logger = logging.getLogger(__name__)

# logger.setLevel(logging.DEBUG)
# logging.getLogger('traccuracy.matchers._ctc').setLevel(logging.DEBUG)


class MotileWidget(QWidget):
    def __init__(self, viewer: "napari.viewer.Viewer", graph_layer=False):
        super().__init__()
        self.viewer = viewer
        self.graph_layer = graph_layer

        main_layout = QVBoxLayout()

        # Select Labels layer
        layer_group = QGroupBox("Select Input Layer")
        layer_layout = QHBoxLayout()
        self.layer_selection_box = QComboBox()
        for layer in viewer.layers:
            if isinstance(layer, Labels):
                self.layer_selection_box.addItem(layer.name)
        if len(self.layer_selection_box) == 0:
            self.layer_selection_box.addItem("None")
        layer_layout.addWidget(self.layer_selection_box)
        layer_group.setLayout(layer_layout)
        main_layout.addWidget(layer_group)

        # Data-specific Hyperparameters section
        hyperparameters_group = QGroupBox("Data-Specific Hyperparameters")
        hyperparameters_layout = QFormLayout()
        self.max_edge_distance_spinbox = QDoubleSpinBox()
        self.max_edge_distance_spinbox.setValue(50)
        self.max_edge_distance_spinbox.setRange(1, 1e10)
        self.max_edge_distance_spinbox.setDecimals(1)
        hyperparameters_layout.addRow("Max Move Distance:", self.max_edge_distance_spinbox)
        hyperparameters_group.setLayout(hyperparameters_layout)
        main_layout.addWidget(hyperparameters_group)

        
        # Constraints section
        constraints_group = QGroupBox("Constraints")
        constraints_layout = QFormLayout()
        #self.max_parents_spinbox = QSpinBox()
        #self.max_parents_spinbox.setValue(1)
        self.max_children_spinbox = QSpinBox()
        self.max_children_spinbox.setValue(2)
        #constraints_layout.addRow("Max Parents:", self.max_parents_spinbox)
        constraints_layout.addRow("Max Children:", self.max_children_spinbox)
        constraints_group.setLayout(constraints_layout)
        main_layout.addWidget(constraints_group)

        # Constant Costs section
        constant_costs_group = QGroupBox("Constant Costs")
        constant_costs_layout = QVBoxLayout()
        
        appear_layout = QHBoxLayout()
        self.appear_spinbox = QDoubleSpinBox()
        self.appear_spinbox.setValue(30)
        self.appear_spinbox.setRange(0.0, 1e10)
        self.appear_spinbox.setDecimals(1)
        self.appear_checkbox = QCheckBox("Appear")
        self.appear_checkbox.setChecked(True)
        self.appear_checkbox.stateChanged.connect(self._on_toggle_cost_appear)
        appear_layout.addWidget(self.appear_checkbox)
        appear_layout.addWidget(self.appear_spinbox)
        constant_costs_layout.addLayout(appear_layout)

        division_layout = QHBoxLayout()
        self.division_spinbox = QDoubleSpinBox()
        self.appear_spinbox.setValue(20)
        self.division_spinbox.setRange(0.0, 1e10)
        self.division_spinbox.setDecimals(1)
        self.division_checkbox = QCheckBox("Division")
        division_layout.addWidget(self.division_checkbox)
        division_layout.addWidget(self.division_spinbox)
        self.division_spinbox.hide()
        self.division_checkbox.stateChanged.connect(self._on_toggle_cost_division)
        constant_costs_layout.addLayout(division_layout)

        constant_costs_group.setLayout(constant_costs_layout)
        main_layout.addWidget(constant_costs_group)

        # Feature-based Costs section
        feature_costs_group = QGroupBox("Feature-based Costs")
        feature_costs_layout = QVBoxLayout()

        # Distance row
        distance_layout = QHBoxLayout()
        self.distance_checkbox = QCheckBox("Distance")
        self.distance_checkbox.setChecked(True)
        self.distance_checkbox.stateChanged.connect(self._on_toggle_distance_cost)
        distance_layout.addWidget(self.distance_checkbox)

        distance_params_layout = QFormLayout()
        self.distance_weight_spinbox = QDoubleSpinBox()
        self.distance_weight_spinbox.setRange(-1e10, 1e10)
        self.distance_weight_spinbox.setValue(1)
        self.distance_offset_spinbox = QDoubleSpinBox()
        self.distance_offset_spinbox.setRange(-1e10, 1e10)
        self.distance_offset_spinbox.setValue(-20)
        self.distance_offset_spinbox.setDecimals(1)
        distance_params_layout.addRow("Weight:", self.distance_weight_spinbox)
        distance_params_layout.addRow("Bias:", self.distance_offset_spinbox)
        self.distance_params_widget = QWidget()
        self.distance_params_widget.setLayout(distance_params_layout)
        distance_layout.addWidget(self.distance_params_widget)

        feature_costs_layout.addLayout(distance_layout)

        # IOU row
        """iou_layout = QHBoxLayout()
        self.iou_checkbox = QCheckBox("IOU")
        self.iou_weight_spinbox = QDoubleSpinBox()
        self.iou_offset_spinbox = QDoubleSpinBox()
        iou_layout.addWidget(self.iou_checkbox)
        iou_layout.addWidget(QLabel("Weight:"))
        iou_layout.addWidget(self.iou_weight_spinbox)
        iou_layout.addWidget(QLabel("Offset:"))
        iou_layout.addWidget(self.iou_offset_spinbox)
        feature_costs_layout.addLayout(iou_layout)"""

        feature_costs_group.setLayout(feature_costs_layout)
        main_layout.addWidget(feature_costs_group)

        # Specify name text box
        run_group = QGroupBox("Run")
        run_layout = QVBoxLayout()
        run_name_layout = QFormLayout()
        self.run_name = QLineEdit("tracks")
        run_name_layout.addRow("Run Name:", self.run_name)
        run_layout.addLayout(run_name_layout)

        # Generate Tracks button
        generate_tracks_btn = QPushButton("Generate Tracks")
        generate_tracks_btn.clicked.connect(self._on_click_generate_tracks)
        run_layout.addWidget(generate_tracks_btn)
        run_group.setLayout(run_layout)
        main_layout.addWidget(run_group)

        # Original layout elements
        # btn = QPushButton("Generate Graph")
        # btn.clicked.connect(self._on_click)
        """graph_ui_group = QGroupBox("Graph UI Control")
        graph_ui_layout = QVBoxLayout()
        self.graph_layer_selection_box = QComboBox()
        for layer in viewer.layers:
            if isinstance(layer, Labels):
                self.graph_layer_selection_box.addItem(layer.name)
        if len(self.graph_layer_selection_box) == 0:
            self.graph_layer_selection_box.addItem("None")
        graph_ui_layout.addWidget(self.graph_layer_selection_box)

        self.thickness_slider = QSlider()
        self.thickness_slider.setOrientation(Qt.Horizontal)
        self.thickness_slider.setRange(1, 100)
        self.thickness_slider.setValue(10)
        self.thickness_slider.valueChanged.connect(self.update_thickness)
        graph_ui_group.setLayout(layer_layout)
        main_layout.addWidget(graph_ui_group)"""


        # original_layout = QHBoxLayout()
        # original_layout.addWidget(btn)
        # original_layout.addWidget(self.slider)

        # main_layout.addLayout(original_layout)

        self.setLayout(main_layout)

    def _on_click(self):
        # Original click event logic
        pass

    def get_max_edge_distance(self):
        return self.max_edge_distance_spinbox.value()

    def get_max_parents(self):
        return self.max_parents_spinbox.value()

    def get_max_children(self):
        return self.max_children_spinbox.value()

    def get_appear_cost(self):
        return self.appear_spinbox.value() if self.appear_checkbox.isChecked() else None

    def get_division_cost(self):
        return self.division_spinbox.value() if self.division_checkbox.isChecked() else None

    def get_distance_weight(self):
        return self.distance_weight_spinbox.value() if self.distance_checkbox.isChecked() else None

    def get_distance_offset(self):
        return self.distance_offset_spinbox.value() if self.distance_checkbox.isChecked() else None

    def get_iou_weight(self):
        return self.iou_weight_spinbox.value() if self.iou_checkbox.isChecked() else None

    def get_iou_offset(self):
        return self.iou_offset_spinbox.value() if self.iou_checkbox.isChecked() else None
    
    def get_run_name(self):
        return self.run_name.text()
    
    def get_labels_layer(self):
        curr_text = self.layer_selection_box.currentText()
        if curr_text == "None":
            return None
        return self.viewer.layers[curr_text]
    
    def _on_toggle_cost_division(self):
        if self.division_checkbox.isChecked():
            self.division_spinbox.show()
        else:
            self.division_spinbox.hide()
    
    def _on_toggle_cost_appear(self):
        if self.appear_checkbox.isChecked():
            self.appear_spinbox.show()
        else:
            self.appear_spinbox.hide()

    def _on_toggle_distance_cost(self):
        if self.distance_checkbox.isChecked():
            self.distance_params_widget.show()
            #self.distance_weight_spinbox.show()
            #self.distance_offset_spinbox.show()
        else:
            self.distance_params_widget.hide()
            #self.distance_weight_spinbox.hide()
            #self.distance_offset_spinbox.hide()

    def _on_click_generate_tracks(self):
        # Logic for generating tracks
        labels_layer = self.get_labels_layer()
        if labels_layer is None:
            return
        segmentation = labels_layer.data

        print(f"Segmentation shape: {segmentation.shape}")
        cand_graph = graph_from_segmentation(segmentation, self.get_max_edge_distance())
        print(f"Cand graph has {cand_graph.number_of_nodes()} nodes")

        solution, solver = solve_with_motile(cand_graph, self)
        solution_nx_graph = get_solution_nx_graph(solution, solver, cand_graph)
        track_data, track_props, track_edges = to_napari_tracks_layer(solution_nx_graph)

        self.viewer.add_tracks(track_data, properties=track_props, graph=track_edges, name=self.get_run_name())
        print(self.graph_layer)
        if self.graph_layer:
            print("Adding graph layer")
            from ._graph_layer_utils import to_napari_graph_layer
            graph_layer = to_napari_graph_layer(solution_nx_graph, "Graph " + self.get_run_name(), loc_keys=("t", "y", "x"))
            self.viewer.add_layer(graph_layer)

    def update_thickness(self, value):
        self.viewer.dims.thickness = (value, ) * self.viewer.dims.ndim