import logging

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

from motile_plugin.backend.motile_run import MotileRun
from motile_plugin.backend.solve import solve

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
    solver_update = Signal()

    def __init__(self, viewer: Viewer):
        super().__init__()
        self.viewer: Viewer = viewer

        # Declare napari layers for displaying outputs (managed by the widget)
        self.output_seg_layer: Labels | None = None
        self.tracks_layer: Tracks | None = None

        # Create sub-widgets and connect signals
        self.edit_run_widget = RunEditor(self.viewer)
        self.edit_run_widget.start_run.connect(self._generate_tracks)

        self.view_run_widget = RunViewer()
        self.view_run_widget.edit_run.connect(self.edit_run)
        self.view_run_widget.hide()
        self.solver_update.connect(self.view_run_widget.solver_event_update)

        self.run_list_widget = RunsList()
        self.run_list_widget.view_run.connect(self.view_run_napari)

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
        if run.output_segmentation is not None:
            self.output_seg_layer = Labels(
                run.output_segmentation[:, 0], name=run.run_name + "_seg"
            )
            self.viewer.add_layer(self.output_seg_layer)
        else:
            self.output_seg_layer = None

        if run.tracks is None or run.tracks.number_of_nodes() == 0:
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
            self.viewer.add_layer(self.tracks_layer)

    def view_run_napari(self, run: MotileRun) -> None:
        """Populates the run viewer and the napari layers with the output
        of the provided run.

        Args:
            run (MotileRun): The run to view
        """
        self.view_run_widget.update_run(run)
        self.edit_run_widget.hide()
        self.view_run_widget.show()
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
        self.run_list_widget.runs_list.clearSelection()
        self.remove_napari_layers()

    def _generate_tracks(self, run: MotileRun) -> None:
        """Called when we start solving a new run. Switches from run editor to run viewer
        and starts solving of the new run in a separate thread to avoid blocking

        Args:
            run (MotileRun): Start solving this motile run.
        """
        run.status = "initializing"
        self.run_list_widget.add_run(run, select=True)
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
        if run.input_segmentation is not None:
            input_data = run.input_segmentation
        elif run.input_points is not None:
            input_data = run.input_points
        else:
            raise ValueError("Must have one of input segmentation or points")
        run.tracks = solve(
            run.solver_params,
            input_data,
            lambda event_data: self._on_solver_event(run, event_data),
        )
        if run.input_segmentation is not None:
            run.output_segmentation = relabel_segmentation(
                run.tracks, run.input_segmentation
            )
        return run

    def _on_solver_event(self, run: MotileRun, event_data: dict) -> None:
        """Parse the solver event and set the run status and gap accordingly.
        Also emits a solver_update event to tell the run viewer to update.
        Note: This will simply tell the run viewer to refresh its plot and
        status. If the run viewer is not viewing this run, it will refresh
        anyways, which is pointless but not harmful.

        Args:
            run (MotileRun): The run that the solver is working on
            event_data (dict): The solver event data from ilpy.EventData
        """
        event_type = event_data["event_type"]
        if (
            event_type in ["PRESOLVE", "PRESOLVEROUND"]
            and run.status != "presolving"
        ):
            run.status = "presolving"
            run.gaps = (
                []
            )  # try this to remove the weird initial gap for gurobi
            self.solver_update.emit()
        elif event_type in ["MIPSOL", "BESTSOLFOUND"]:
            run.status = "solving"
            gap = event_data["gap"]
            run.gaps.append(gap)
            self.solver_update.emit()

    def _on_solve_complete(self, run: MotileRun) -> None:
        """Called when the solver thread returns. Updates the run status to done
        and tells the run viewer to update.

        Args:
            run (MotileRun): The completed run
        """
        run.status = "done"
        self.solver_update.emit()
        self.view_run_napari(run)

    def _title_widget(self) -> QWidget:
        """Create the title and intro paragraph widget, with links to docs

        Returns:
            QWidget: A widget introducing the motile plugin and linking to docs
        """
        richtext = r"""<h3>Tracking with Motile</h3>
        <p>This plugin uses the
        <a href="https://funkelab.github.io/motile/"><font color=yellow>motile</font></a> library to
        track objects with global optimization. See the
        <a href="https://funkelab.github.io/motile_napari_plugin/"><font color=yellow>user guide</font></a>
        for a tutorial to the plugin functionality."""
        label = QLabel(richtext)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        return label
