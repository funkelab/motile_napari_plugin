import logging
from warnings import warn

from motile_plugin.backend.motile_run import MotileRun
from motile_plugin.backend.solve import solve
from motile_plugin.backend.solver_params import SolverParams
from motile_toolbox.utils import relabel_segmentation
from motile_toolbox.visualization import to_napari_tracks_layer
from napari import Viewer
from napari.layers import Labels, Tracks
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import thread_worker

from .run_editor import RunEditor
from .run_viewer import RunViewer
from .runs_list import RunsList

logger = logging.getLogger(__name__)


class MotileWidget(QWidget):
    """The main widget for the motile napari plugin. Coordinates sub-widgets
    and calls the back-end motile solver.
    """

    # A signal for passing events from the motile solver to the run view widget
    # To provide updates on progress of the solver
    solver_event = Signal(dict)

    def __init__(self, viewer: Viewer):
        super().__init__()
        self.viewer: Viewer = viewer

        # Declare napari layers for displaying outputs (managed by the widget)
        self.output_seg_layer: Labels | None = None
        self.tracks_layer: Tracks | None = None

        # Create sub-widgets and connect signals
        self.edit_run_widget = RunEditor(
            "new_run", SolverParams(), self.viewer.layers
        )
        self.edit_run_widget.create_run.connect(self._generate_tracks)
        self.edit_run_widget.refresh_layer_button.clicked.connect(
            self._update_editor_layers
        )

        self.view_run_widget = RunViewer()
        self.view_run_widget.hide()
        self.solver_event.connect(self.view_run_widget.solver_event_update)

        self.run_list_widget = RunsList()
        self.run_list_widget.view_run.connect(self.view_run_napari)
        self.run_list_widget.edit_run.connect(self.edit_run)

        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._title_widget())
        main_layout.addWidget(self.view_run_widget)
        main_layout.addWidget(self.edit_run_widget)
        main_layout.addWidget(self.run_list_widget)
        self.setLayout(main_layout)

    def remove_napari_layers(self) -> None:
        """Remove the currently stored layers from the napari viewer, if present"""
        if (
            self.output_seg_layer
            and self.output_seg_layer in self.viewer.layers
        ):
            self.viewer.layers.remove(self.output_seg_layer)
        if self.tracks_layer and self.tracks_layer in self.viewer.layers:
            self.viewer.layers.remove(self.tracks_layer)

    def update_napari_layers(self, run: MotileRun) -> None:
        """Remove the old napari layers and update them according to the run output.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            run (MotileRun): The run outputs to visualize in napari.
        """
        # Remove old layers if necessary
        self.remove_napari_layers()

        # Create new layers
        self.output_seg_layer = Labels(
            run.output_segmentation[:, 0], name=run.run_name + "_seg"
        )
        if run.tracks is None or run.tracks.number_of_nodes() == 0:
            warn(f"No tracks found for run {run.run_name}", stacklevel=2)
            self.tracks_layer = None
        else:
            track_data, track_props, track_edges = to_napari_tracks_layer(
                run.tracks
            )
            self.tracks_layer = Tracks(
                track_data,
                properties=track_props,
                graph=track_edges,
                name=run.run_name + "_tracks",
                tail_length=3,
            )

        # Add layers to the viewer
        if self.tracks_layer is not None:
            self.viewer.add_layer(self.output_seg_layer)
            self.viewer.add_layer(self.tracks_layer)

    def view_run(self, run: MotileRun):
        """View the provided run in the run viewer. Does not include
        adding the layers to napari.
        Args:
            run (MotileRun): The run to view
        """
        self.view_run_widget.reset_progress()
        self.view_run_widget.update_run(run)
        self.edit_run_widget.hide()
        self.view_run_widget.show()

    def view_run_napari(self, run: MotileRun) -> None:
        """Populates the run viewer and the napari layers with the output
        of the provided run.
        Note: this needs to be a single function so we can register it with a signal
        Args:
            run (MotileRun): The run to view
        """
        self.view_run(run)
        self.update_napari_layers(run)

    def edit_run(self, run: MotileRun | None):
        """Create or edit a new run in the run editor. Also removes solution layers
        from the napari viewer.
        Args:
            run (MotileRun | None): Initialize the new run with the parameters and name
                from this run. If not provided, uses the SolverParams default values.
        """
        self.view_run_widget.hide()
        self.edit_run_widget.show()
        if run:
            self.edit_run_widget.new_run(run)
        self.remove_napari_layers()

    def _generate_tracks(self, run: MotileRun) -> None:
        """Called when we start solving a new run. Switches from run editor to run viewer
        and starts solving of the new run in a separate thread to avoid blocking
        """
        self.view_run(run)
        self.view_run_widget.set_solver_label("initializing")
        worker = self.solve_with_motile(run)
        worker.returned.connect(self._on_solve_complete)
        worker.start()

    @thread_worker
    def solve_with_motile(self, run: MotileRun) -> MotileRun:
        """Runs the solver and relabels the segmentation to match
        the solution graph.
        Emits: self.solver_event when the solver provides an update
        (will be emitted from the thread, which is why it needs to be an
        event and not just a normal function callback)

        Args:
            run (MotileRun): A run with name, parameters, and input segmentation,
                but not including the output graph or segmentation.

        Returns:
            MotileRun: The provided run with the output graph and segmentation included.
        """
        run.tracks = solve(
            run.solver_params, run.input_segmentation, self.solver_event.emit
        )
        run.output_segmentation = relabel_segmentation(
            run.tracks, run.input_segmentation
        )
        return run

    def _on_solve_complete(self, run: MotileRun) -> None:
        """Called when the solver thread returns. Adds the completed run
        to the runs list and selects it. Updates the solver status label to done.

        Args:
            run (MotileRun): The completed run
        """
        self.run_list_widget.add_run(run.copy(), select=True)
        self.view_run_widget.set_solver_label("done")

    def _title_widget(self) -> QWidget:
        """Create the title and intro paragraph widget, with links to docs

        Returns:
            QWidget: A widget introducing the motile plugin and linking to docs
        """
        richtext = r"""<h3>Tracking with Motile</h3>
        <p>This plugin uses the
        <a href="https://funkelab.github.io/motile/">motile</a> library to
        track objects with global optimization. See the
        <a href="https://funkelab.github.io/motile-napari-plugin/">user guide</a>
        for a tutorial to the plugin functionality."""
        label = QLabel(richtext)
        label.setWordWrap(True)
        return label

    def _update_editor_layers(self):
        self.edit_run_widget.update_labels_layers(self.viewer.layers)
