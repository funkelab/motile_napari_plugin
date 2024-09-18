from functools import partial
from pathlib import Path
from warnings import warn

import pyqtgraph as pg
from fonticon_fa6 import FA6S
from motile_toolbox.candidate_graph import NodeAttr
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible
from superqt.fonticon import icon as qticon

from motile_plugin.backend.motile_run import MotileRun

from .params_viewer import SolverParamsViewer


class RunViewer(QGroupBox):
    """A widget for viewing in progress or completed runs, including
    the progress of the solver and the parameters. Can also save the whole
    run or export the tracks to CSV.
    Output tracks and segmentation are visualized separately in napari layers.
    """

    edit_run = Signal(object)

    def __init__(self):
        super().__init__(title="Run Viewer")

        # define attributes
        self.run: MotileRun | None = None
        self.params_widget = SolverParamsViewer()
        self.solver_label: QLabel
        self.gap_plot: pg.PlotWidget

        # Define persistent file dialogs for saving and exporting
        self.save_run_dialog = self._save_dialog()
        self.export_tracks_dialog = self._export_tracks_dialog()

        # Create layout and add subwidgets
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._progress_widget())
        main_layout.addWidget(self.params_widget)
        main_layout.addWidget(self._save_and_export_widget())
        main_layout.addWidget(self._back_to_edit_widget())
        self.setLayout(main_layout)

    def update_run(self, run: MotileRun):
        """Update the run being viewed. Changes the title, solver status and
        gap plot, and parameters being displayed.

        Args:
            run (MotileRun): The new run to display
        """
        self.run = run
        run_time = run.time.strftime("%m/%d/%y, %H:%M:%S")
        run_name_view = f"{run.run_name} ({run_time})"
        self.setTitle("Run Viewer: " + run_name_view)
        self.solver_event_update()
        self.params_widget.new_params.emit(run.solver_params)

    def _save_and_export_widget(self) -> QWidget:
        """Create a widget for saving and exporting tracking results.

        Returns:
            QWidget: A widget containing a save button and an export tracks
                button.
        """
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Save button
        icon = qticon(FA6S.floppy_disk, color="white")
        save_run_button = QPushButton(icon=icon, text="Save run")
        save_run_button.clicked.connect(self.save_run)
        layout.addWidget(save_run_button)

        # create button to export tracks
        export_tracks_btn = QPushButton("Export tracks to CSV")
        export_tracks_btn.clicked.connect(self.export_tracks)
        layout.addWidget(export_tracks_btn)

        widget.setLayout(layout)
        return widget

    def _back_to_edit_widget(self) -> QWidget:
        """Create a widget for navigating back to the run editor with different
        parameters.

        Returns:
            QWidget: A widget with two buttons: one for navigating back to the
                previous run editor state, and one for populating the run
                editor with the currently viewed run's parameters.
        """
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # create back to editing button
        edit_run_button = QPushButton("Back to editing")
        edit_run_button.clicked.connect(partial(self.edit_run.emit, None))
        layout.addWidget(edit_run_button)

        # new run from this config button
        run_from_config_button = QPushButton("Edit this run")
        run_from_config_button.clicked.connect(self._emit_run)
        layout.addWidget(run_from_config_button)

        widget.setLayout(layout)
        return widget

    def _emit_run(self):
        """Emit the edit_run signal with the current run. Used to populate
        the run editor with the current run's parameters.
        """
        self.edit_run.emit(self.run)  # Note: this may cause memory leak
        # Can use weakref if that happens
        # https://github.com/Carreau/napari/commit/cd079e9dcb62de115833ea1b6bb1b7a0ab4b78d1

    def _progress_widget(self) -> QWidget:
        """Create a widget containing solver progress and status.

        Returns:
            QWidget: A widget with a label indicating solver status and
                a collapsible graph of the solver gap.
        """
        widget = QWidget()
        layout = QVBoxLayout()

        self.solver_label = QLabel("")
        self.gap_plot = self._plot_widget()
        collapsable_plot = QCollapsible("Graph of solver gap")
        collapsable_plot.layout().setContentsMargins(0, 0, 0, 0)
        collapsable_plot.addWidget(self.gap_plot)
        collapsable_plot.collapse(animate=False)

        layout.addWidget(self.solver_label)
        layout.addWidget(collapsable_plot)
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        return widget

    def _plot_widget(self) -> pg.PlotWidget:
        """
        Returns:
            pg.PlotWidget: a widget containg an (empty) plot of the solver gap
        """
        gap_plot = pg.PlotWidget()
        gap_plot.setBackground((37, 41, 49))
        styles = {
            "color": "white",
        }
        gap_plot.plotItem.setLogMode(x=False, y=True)
        gap_plot.plotItem.setLabel("left", "Gap", **styles)
        gap_plot.plotItem.setLabel("bottom", "Solver round", **styles)
        return gap_plot

    def _save_dialog(self) -> QFileDialog:
        save_run_dialog = QFileDialog()
        save_run_dialog.setFileMode(QFileDialog.Directory)
        save_run_dialog.setOption(QFileDialog.ShowDirsOnly, True)
        return save_run_dialog

    def _export_tracks_dialog(self) -> QFileDialog:
        export_tracks_dialog = QFileDialog()
        export_tracks_dialog.setFileMode(QFileDialog.AnyFile)
        export_tracks_dialog.setAcceptMode(QFileDialog.AcceptSave)
        export_tracks_dialog.setDefaultSuffix("csv")
        return export_tracks_dialog

    def save_run(self):
        if self.save_run_dialog.exec_():
            directory = self.save_run_dialog.selectedFiles()[0]
            self.run.save(directory)

    def export_tracks(self):
        """Export the tracks from this run to a csv with the following columns:
        t,[z],y,x,id,parent_id,[seg_id]
        Cells without a parent_id will have an empty string for the parent_id.
        Whether or not to include z is inferred from the length of an
        arbitrary node's position attribute. If the nodes have a "seg_id" attribute,
        the "seg_id" column is included.
        """
        default_name = self.run._make_id()
        default_name = f"{default_name}_tracks.csv"
        base_path = Path(self.export_tracks_dialog.directory().path())
        self.export_tracks_dialog.selectFile(str(base_path / default_name))
        if self.export_tracks_dialog.exec_():
            outfile = self.export_tracks_dialog.selectedFiles()[0]
            header = ["t", "z", "y", "x", "id", "parent_id", "seg_id"]
            tracks = self.run.tracks.graph
            _, sample_data = next(iter(tracks.nodes(data=True)))
            ndim = len(sample_data[NodeAttr.POS.value])
            if ndim == 2:
                header = [header[0]] + header[2:]  # remove z
            if "seg_id" not in sample_data:
                header = [header[0:-1]]  # remove seg_id
            with open(outfile, "w") as f:
                f.write(",".join(header))
                for node_id, data in tracks.nodes(data=True):
                    parents = list(tracks.predecessors(node_id))
                    parent_id = "" if len(parents) == 0 else parents[0]
                    seg_id = data.get("seg_id", "")
                    row = [
                        data[NodeAttr.TIME.value],
                        *data[NodeAttr.POS.value],
                        node_id,
                        parent_id,
                        seg_id,
                    ]
                    f.write("\n")
                    f.write(",".join(map(str, row)))
        else:
            warn("Exporting aborted", stacklevel=2)

    def _set_solver_label(self, status: str):
        message = "Solver status: " + status
        self.solver_label.setText(message)

    def solver_event_update(self):
        self._set_solver_label(self.run.status)
        self.gap_plot.getPlotItem().clear()
        gaps = self.run.gaps
        if gaps is not None and len(gaps) > 0:
            self.gap_plot.getPlotItem().plot(range(len(gaps)), gaps)

    def reset_progress(self):
        self._set_solver_label("not running")
        self.gap_plot.getPlotItem().clear()
