
import logging

from motile_toolbox.utils import relabel_segmentation
from motile_toolbox.visualization import to_napari_tracks_layer
from napari.layers import Labels, Layer
from qtpy.QtCore import Signal
from functools import partial
from qtpy.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
)
from superqt.utils import thread_worker

from ._qwidget_components import (
    LayerSelectBox,
)
from .motile_run import MotileRun
from .motile_solver import MotileSolver
from .runs_list_widget import RunsList
from .solver_params import SolverParams
from .solver_params_widget import SolverParamsWidget

logger = logging.getLogger(__name__)


class RunEditor(QWidget):
    create_run = Signal(MotileRun)
    def __init__(self, run_name, solver_params, layers):
        # TODO: Don't pass static layers
        super().__init__()
        self.run_name: QLineEdit
        self.layers: list[Layer]
        self.layer_selection_box: QComboBox
        self.solver_params_widget = SolverParamsWidget(solver_params, editable=True)
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._ui_select_labels_layer(layers))
        main_layout.addWidget(self.solver_params_widget)
        main_layout.addWidget(self._ui_run_motile(run_name))
        self.setLayout(main_layout)

    def _ui_select_labels_layer(self, layers) -> QGroupBox:
        # Select Labels layer
        layer_group = QGroupBox("Select Input Layer")
        layer_layout = QHBoxLayout()
        self.layer_selection_box = QComboBox()
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
        if len(self.layer_selection_box) == 0:
            self.layer_selection_box.addItem("None")

    def get_labels_layer(self) -> str:
        layer_name = self.layer_selection_box.currentText()
        if layer_name == "None":
            return None
        return self.layers[self.layer_selection_box.currentText()]

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
        input_seg = self.get_labels_layer().data
        params = self.solver_params_widget.solver_params
        return MotileRun(run_name=run_name, solver_params=params, input_segmentation=input_seg)
    
    def emit_run(self):
        self.create_run.emit(self.get_run())

    def _print_parameters(self):
        print(f"Solving with parameters {self.solver_params_widget.solver_params}")


class RunViewer(QWidget):
    def __init__(self, run: MotileRun):
        super().__init__()
        self.run = run
        if run:
            self.run_name_widget = QLabel(self.run.run_name)
            self.params_widget = SolverParamsWidget(run.solver_params, editable=False)
        else:
            self.run_name_widget = QLabel("temp")
            self.params_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.run_name_widget)
        self.main_layout.addWidget(self.params_widget)
        self.setLayout(self.main_layout)

    def update_run(self, run: MotileRun):
        print(f"Updating run with params {run.solver_params}")
        self.run = run
        self.run_name_widget.setText(self.run.run_name)
        self.main_layout.removeWidget(self.params_widget)
        self.params_widget = SolverParamsWidget(run.solver_params, editable=False)
        self.main_layout.addWidget(self.params_widget)
        # self.update()



class MotileWidget(QWidget):
    """
    For Runs, a couple options:
    - view (read-only)
    - load config (and input seg?) to current run (e.g. New run from loaded run)
    - delete
    """

    def __init__(self, viewer, graph_layer=False, storage_path="./motile_results"):
        super().__init__()
        self.viewer = viewer
        self.graph_layer = graph_layer

        self.in_progress_params = SolverParams()
        self.in_progress_name = "new_run"

        main_layout = QVBoxLayout()
        self.edit_run_widget = RunEditor("new_run", SolverParams(), self.viewer.layers)
        self.edit_run_widget.create_run.connect(self._generate_tracks)

        self.view_run_widget = RunViewer(None)
        self.view_run_widget.hide()

        self.run_list_widget = RunsList(storage_path)
        self.run_list_widget.view_run.connect(self.view_run)
        self.run_list_widget.edit_run.connect(self.edit_run)

        self.running_label = QLabel("Solver is running")
        self.running_label.hide()

        main_layout.addWidget(self.view_run_widget)
        main_layout.addWidget(self.edit_run_widget)
        main_layout.addWidget(self.running_label)
        main_layout.addWidget(self.run_list_widget)
        self.setLayout(main_layout)

    def view_run(self, run: MotileRun):
        # TODO: remove old layers from napari and replace with new
        self.view_run_widget.update_run(run)
        self.edit_run_widget.hide()
        self.view_run_widget.show()

        # Add layers to Napari
        self.viewer.add_labels(run.output_segmentation, name=run.run_name + "_seg",)
        # add tracks
        if run.tracks is None or run.tracks.number_of_nodes() == 0:
            # TODO: Handle this edge case without error
            # warn("No tracks selected.")
            self.viewer.add_tracks([], name=run.run_name)
        track_data, track_props, track_edges = to_napari_tracks_layer(
            run.tracks, location_keys=self._get_pos_keys(run)
        )
        self.viewer.add_tracks(
            track_data, properties=track_props, graph=track_edges,
            name=run.run_name)

        logger.debug(self.graph_layer)
        if self.graph_layer:
            print("Adding graph layer")
            from ._graph_layer_utils import to_napari_graph_layer
            graph_layer = to_napari_graph_layer(run.tracks, "Graph " + self.get_run_name(), loc_keys=("t", "y", "x"))
            self.viewer.add_layer(graph_layer)

    def _get_pos_keys(self, run: MotileRun):
        if run.input_segmentation is None:
            print("Cannot infer position keys")
            return None
        if len(run.input_segmentation.shape) == 3:
            return ["y", "x"]
        elif len(run.input_segmentation.shape) == 4:
            return ["z", "y", "x"]

    def edit_run(self):
        self.view_run_widget.hide()
        self.edit_run_widget.show()


    def _generate_tracks(self, run):
        print(f"Creating run {run}")
        # Logic for generating tracks
        logger.debug("Segmentation shape: %s", run.input_segmentation.shape)
        # do this in a separate thread so we can parse stdout and not block
        self.running_label.show()
        worker = self.solve_with_motile(run)
        worker.returned.connect(self._on_solve_complete)
        worker.start()


    @thread_worker
    def solve_with_motile(
        self,
        run: MotileRun
        ):
        position_keys = self._get_pos_keys(run)
        solver = MotileSolver(run.solver_params)
        run.tracks = solver.solve(run.input_segmentation, position_keys=position_keys)
        run.output_segmentation = relabel_segmentation(run.tracks, run.input_segmentation)
        return run

    def _on_solve_complete(self, run: MotileRun):
        self.running_label.hide()
        self.run_list_widget.add_run(run)
        self.run_list_widget.save_run(run)





