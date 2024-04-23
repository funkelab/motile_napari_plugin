
from qtpy.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QFileDialog,
    QHBoxLayout,
)
from .solver_params import SolverParamsWidget
from motile_plugin.backend.motile_run import MotileRun
from motile_plugin.backend.solver_params import SolverParams
from napari._qt.qt_resources import QColoredSVGIcon
import importlib.resources
from warnings import warn
import networkx as nx
import json
from pathlib import Path
import pyqtgraph as pg


class RunViewer(QWidget):
    def __init__(self, run: MotileRun):
        super().__init__()
        self.run = run
        if run:
            self.run_name_widget = QLabel(self._run_name_view(self.run))
            self.params_widget = SolverParamsWidget(run.solver_params, editable=False)
        else:
            self.run_name_widget = QLabel("temp")
            self.params_widget = SolverParamsWidget(SolverParams(), editable=False)
        
        # Define persistent file dialogs for saving and exporting
        self.save_run_dialog = self._save_dialog()
        self.export_tracks_dialog = self._export_tracks_dialog()

        export_tracks_btn = QPushButton("Export tracks")
        export_tracks_btn.clicked.connect(self.export_tracks)

        self.solver_label: QLabel
        self.gap_plot = pg.PlotWidget

        main_layout = QVBoxLayout()
        main_layout.addWidget(self._title_widget())
        main_layout.addWidget(export_tracks_btn)
        main_layout.addWidget(self._progress_widget())
        main_layout.addWidget(self.params_widget)
        self.setLayout(main_layout)

    def update_run(self, run: MotileRun):
        self.run = run
        self.run_name_widget.setText(self._run_name_view(self.run))
        self.params_widget.new_params.emit(run.solver_params)

    def _run_name_view(self, run: MotileRun) -> str:
        run_time = run.time.strftime('%m/%d/%y, %H:%M:%S')
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
        layout.addWidget(self.solver_label)
        layout.addWidget(self.gap_plot)
        layout.setContentsMargins(0, 0, 0, 0)
        progress_widget.setLayout(layout)
        return progress_widget

    def set_solver_label(self, status: str):
        message = "Solver status: " + status
        self.solver_label.setText(message)
    
    def _plot_widget(self) -> pg.PlotWidget:
        gap_plot = pg.PlotWidget()
        gap_plot.setBackground((37, 41, 49))
        styles = {"color": "white",}
        gap_plot.setLabel("left", "Gap", **styles)
        gap_plot.setLabel("bottom", "Solver round", **styles)
        gap_plot.getPlotItem().setLogMode(x=False, y=True)
        return gap_plot
    
    def plot_gaps(self):
        gaps = self.run.gaps
        self.gap_plot.getPlotItem().plot(range(len(gaps)), gaps)

    def _save_dialog(self) -> QFileDialog:
        save_run_dialog = QFileDialog()
        save_run_dialog.setFileMode(QFileDialog.Directory)
        save_run_dialog.setOption(QFileDialog.ShowDirsOnly, True)
        return save_run_dialog
    
    def _export_tracks_dialog(self) -> QFileDialog:
        export_tracks_dialog = QFileDialog()
        export_tracks_dialog.setFileMode(QFileDialog.AnyFile)
        export_tracks_dialog.setAcceptMode(QFileDialog.AcceptSave)
        export_tracks_dialog.setDefaultSuffix("json")
        return export_tracks_dialog
    
    def save_run(self):
        if self.save_run_dialog.exec_():
            directory = self.save_run_dialog.selectedFiles()[0]
            self.run.save(directory)
        else:
            warn("Saving aborted")

    def export_tracks(self):
        default_name = MotileRun._make_directory(self.run.time, self.run.run_name)
        default_name = f"{default_name}_tracks.json"
        base_path = Path(self.export_tracks_dialog.directory().path())
        self.export_tracks_dialog.selectFile(str(base_path / default_name))
        if self.export_tracks_dialog.exec_():
            outfile = self.export_tracks_dialog.selectedFiles()[0]
            with open(outfile, 'w') as f:
                json.dump(nx.node_link_data(self.run.tracks), f)
        else:
            warn("Exporting aborted")

    def solver_event_update(self, event_data):
        event_type = event_data["event_type"]
        if event_type in ["PRESOLVE", "PRESOLVEROUND"]:
            self.set_solver_label("presolving")
            self.run.gaps = []  # try this to remove the weird initial gap for gurobi
        elif event_type in ["MIPSOL", "BESTSOLFOUND"]:
            self.set_solver_label("solving")
            gap = event_data["gap"]
            print(f"{gap=}")
            self.run.gaps.append(event_data["gap"])
            self.plot_gaps()
    
    def reset_progress(self):
        self.gap_plot.getPlotItem().clear()

