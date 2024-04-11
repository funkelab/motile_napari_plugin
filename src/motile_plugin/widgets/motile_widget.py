
import logging

from motile_toolbox.utils import relabel_segmentation
from motile_toolbox.visualization import to_napari_tracks_layer
from napari.layers import Labels, Tracks
from napari import Viewer
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from superqt.utils import thread_worker
from warnings import warn
import numpy as np

from motile_plugin.backend.motile_run import MotileRun
from motile_plugin.backend.solve import solve
from motile_plugin.backend.solver_params import SolverParams
from .runs_list import RunsList
from .run_editor import RunEditor
from .run_viewer import RunViewer
from .solver_status import SolverStatus
from .solver_params import SolverParamsWidget

logger = logging.getLogger(__name__)


class MotileWidget(QWidget):
    def __init__(self, viewer, graph_layer=False, multiseg=False, storage_path="./motile_results"):
        super().__init__()
        self.viewer: Viewer = viewer
        self.graph_layer = graph_layer
        self.multiseg = multiseg

        self.input_seg_layer : Labels | None = None
        self.output_seg_layer: Labels | None = None
        self.tracks_layer: Tracks | None = None

        main_layout = QVBoxLayout()
        self.edit_run_widget = RunEditor("new_run", SolverParams(), self.viewer.layers, multiseg=multiseg)
        self.edit_run_widget.create_run.connect(self._generate_tracks)

        self.view_run_widget = RunViewer(None)
        self.view_run_widget.hide()

        self.run_list_widget = RunsList(storage_path)
        self.run_list_widget.view_run.connect(self.view_run)
        self.run_list_widget.edit_run.connect(self.edit_run)

        self.solver_status_widget = SolverStatus()
        self.solver_status_widget.hide()

        main_layout.addWidget(self.view_run_widget)
        main_layout.addWidget(self.edit_run_widget)
        main_layout.addWidget(self.solver_status_widget)
        main_layout.addWidget(self.run_list_widget)
        self.setLayout(main_layout)

    def remove_napari_layers(self):
        if self.output_seg_layer and self.output_seg_layer in self.viewer.layers:
            self.viewer.layers.remove(self.output_seg_layer)
        if self.tracks_layer and self.tracks_layer in self.viewer.layers:
            self.viewer.layers.remove(self.tracks_layer)

    def update_napari_layers(self, run):
        self.output_seg_layer = Labels(run.output_segmentation[:, 0], name=run.run_name + "_seg")

        if self.tracks_layer and self.tracks_layer in self.viewer.layers:
            self.viewer.layers.remove(self.tracks_layer)
        if not self.graph_layer:
            # add tracks
            if run.tracks is None or run.tracks.number_of_nodes() == 0:
                warn("No tracks found for run {run.run_name}")
                self.tracks_layer = None
            else:
                track_data, track_props, track_edges = to_napari_tracks_layer(run.tracks)
                self.tracks_layer = Tracks(
                    track_data,
                    properties=track_props,
                    graph=track_edges,
                    name=run.run_name + "_tracks",
                    tail_length=3,
                    )
        else:
            print("Adding graph layer")
            from .._graph_layer_utils import to_napari_graph_layer
            self.tracks_layer = to_napari_graph_layer(run.tracks, "Graph " + self.get_run_name(), loc_keys=("t", "y", "x"))


    def add_napari_layers(self):
        self.viewer.add_layer(self.output_seg_layer)
        self.viewer.add_layer(self.tracks_layer)
        

    def view_run(self, run: MotileRun):
        # TODO: remove old layers from napari and replace with new
        self.view_run_widget.update_run(run)
        self.edit_run_widget.hide()
        self.view_run_widget.show()

        # Add layers to Napari
        self.remove_napari_layers()
        self.update_napari_layers(run)
        self.add_napari_layers()
        

    def edit_run(self, run: MotileRun | None):
        self.view_run_widget.hide()
        self.edit_run_widget.show()
        if run:
            self.edit_run_widget.new_run(run)
        
        self.remove_napari_layers()


    def _generate_tracks(self, run):
        print(f"Creating run {run}")
        # Logic for generating tracks
        logger.debug("Segmentation shape: %s", run.input_segmentation.shape)
        # do this in a separate thread so we can parse stdout and not block
        self.solver_status_widget.show()
        worker = self.solve_with_motile(run)
        worker.returned.connect(self._on_solve_complete)
        worker.start()

    def on_solver_update(self, event_data):
        self.solver_status_widget.update(event_data)
            
    # print(event_data)
    @thread_worker
    def solve_with_motile(
        self,
        run: MotileRun
        ):
        run.tracks = solve(run.solver_params, run.input_segmentation, self.on_solver_update)
        print(f"{run.input_segmentation.shape=}")
        run.output_segmentation = relabel_segmentation(run.tracks, run.input_segmentation)
        print(f"{run.output_segmentation.shape=}")
        return run

    def _on_solve_complete(self, run: MotileRun):
        self.solver_status_widget.hide()
        self.run_list_widget.add_run(run, select=True)
        self.run_list_widget.save_run(run)
        self.view_run(run)
        self.solver_status_widget.reset()





