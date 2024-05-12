import importlib.resources
from pathlib import Path
from warnings import warn

import pyqtgraph as pg
from motile_toolbox.candidate_graph import NodeAttr
from napari._qt.qt_resources import QColoredSVGIcon
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

from motile_plugin.backend.motile_run import MotileRun

from .params_viewer import SolverParamsViewer


class RunViewer(QGroupBox):
    """A widget for viewing in progress or completed runs, including
    the progress of the solver and the parameters. Can also save the whole
    run or export the tracks to CSV.
    Output tracks and segmentation are visualized separately in napari layers.
    """

    edit_run = Signal()

    def __init__(self):
        super().__init__(title="Run Viewer")
        # define attributes
        self.run: MotileRun = None
        self.run_name_widget = QLabel("No run selected")
        self.params_widget = SolverParamsViewer()
        self.solver_label: QLabel
        self.gap_plot: pg.PlotWidget
        # Define persistent file dialogs for saving and exporting
        self.save_run_dialog = self._save_dialog()
        self.export_tracks_dialog = self._export_tracks_dialog()

        # create button to export tracks
        export_tracks_btn = QPushButton("Export tracks to CSV")
        export_tracks_btn.clicked.connect(self.export_tracks)

        # create back to editing button
        edit_run_button = QPushButton("Back to Editing")
        edit_run_button.clicked.connect(self.edit_run.emit)

        # Create layout and add subwidgets
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._title_widget())
        main_layout.addWidget(export_tracks_btn)
        main_layout.addWidget(edit_run_button)
        main_layout.addWidget(self._progress_widget())
        main_layout.addWidget(self.params_widget)
        self.setLayout(main_layout)

    def update_run(self, run: MotileRun):
        self.run = run
        self.run_name_widget.setText(self._run_name_view(self.run))
        self.gap_plot.getPlotItem().clear()
        self.solver_event_update()
        self.params_widget.new_params.emit(run.solver_params)

    def _run_name_view(self, run: MotileRun) -> str:
        run_time = run.time.strftime("%m/%d/%y, %H:%M:%S")
        return f"Viewing {run.run_name} ({run_time})"

    def _save_widget(self):
        resources = importlib.resources.files("motile_plugin.resources")
        icon = QColoredSVGIcon(resources / "save.svg")
        save_run_button = QPushButton(icon=icon.colored("white"))
        save_run_button.clicked.connect(self.save_run)
        return save_run_button

    def _title_widget(self):
        title_widget = QWidget()
        title_layout = QHBoxLayout()
        title_layout.addWidget(self.run_name_widget)
        title_layout.addWidget(self._save_widget())
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_widget.setLayout(title_layout)
        return title_widget

    def _progress_widget(self):
        progress_widget = QWidget()
        layout = QVBoxLayout()
        self.solver_label = QLabel("")
        self.gap_plot = self._plot_widget()
        collapsable_plot = QCollapsible("Graph of solver gap")
        collapsable_plot.layout().setContentsMargins(0, 0, 0, 0)
        collapsable_plot.addWidget(self.gap_plot)
        collapsable_plot.expand(animate=False)
        layout.addWidget(self.solver_label)
        layout.addWidget(collapsable_plot)
        layout.setContentsMargins(0, 0, 0, 0)
        progress_widget.setLayout(layout)
        return progress_widget

    def set_solver_label(self, status: str):
        message = "Solver status: " + status
        self.solver_label.setText(message)

    def _plot_widget(self) -> pg.PlotWidget:
        gap_plot = pg.PlotWidget()
        gap_plot.setBackground((37, 41, 49))
        styles = {
            "color": "white",
        }
        gap_plot.plotItem.setLogMode(x=False, y=True)
        gap_plot.plotItem.setLabel("left", "Gap", **styles)
        gap_plot.plotItem.setLabel("bottom", "Solver round", **styles)
        return gap_plot

    def plot_gaps(self, gaps: list[float]):
        if len(gaps) > 0:
            self.gap_plot.getPlotItem().plot(range(len(gaps)), gaps)
        else:
            self.gap_plot.getPlotItem().clear()

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
        else:
            warn("Saving aborted", stacklevel=2)

    def export_tracks(self):
        """Export the tracks from this run to a csv with the following columns:
        t,[z],y,x,id,parent_id
        Cells without a parent_id will have an empty string for the parent_id.
        Whether or not to include z is inferred from the length of an
        arbitrary node's position attribute.
        """
        default_name = MotileRun._make_directory(
            self.run.time, self.run.run_name
        )
        default_name = f"{default_name}_tracks.csv"
        base_path = Path(self.export_tracks_dialog.directory().path())
        self.export_tracks_dialog.selectFile(str(base_path / default_name))
        if self.export_tracks_dialog.exec_():
            outfile = self.export_tracks_dialog.selectedFiles()[0]
            header = ["t", "z", "y", "x", "id", "parent_id"]
            tracks = self.run.tracks
            _, sample_data = next(iter(tracks.nodes(data=True)))
            ndim = len(sample_data[NodeAttr.POS.value])
            if ndim == 2:
                header = [header[0]] + header[2:]  # remove z
            with open(outfile, "w") as f:
                f.write(",".join(header))
                for node_id, data in tracks.nodes(data=True):
                    parents = list(tracks.predecessors(node_id))
                    parent_id = "" if len(parents) == 0 else parents[0]
                    row = [
                        data[NodeAttr.TIME.value],
                        *data[NodeAttr.POS.value],
                        node_id,
                        parent_id,
                    ]
                    f.write("\n")
                    f.write(",".join(map(str, row)))
        else:
            warn("Exporting aborted", stacklevel=2)

    def solver_event_update(self):
        self.set_solver_label(self.run.status)
        self.plot_gaps(self.run.gaps)

    def reset_progress(self):
        self.set_solver_label("not running")
        self.gap_plot.getPlotItem().clear()
