
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
        
        self.save_run_dialog = QFileDialog()
        self.save_run_dialog.setFileMode(QFileDialog.Directory)
        self.save_run_dialog.setOption(QFileDialog.ShowDirsOnly, True)

        self.export_tracks_dialog = QFileDialog()
        self.export_tracks_dialog.setFileMode(QFileDialog.AnyFile)
        self.export_tracks_dialog.setAcceptMode(QFileDialog.AcceptSave)
        self.export_tracks_dialog.setDefaultSuffix("json")

        title_widget = QWidget()
        title_layout = QHBoxLayout()
        title_layout.addWidget(self.run_name_widget)
        title_layout.addWidget(self._save_widget())
        title_widget.setLayout(title_layout)

        export_tracks_btn = QPushButton("Export tracks")
        export_tracks_btn.clicked.connect(self.export_tracks)

        main_layout = QVBoxLayout()
        main_layout.addWidget(title_widget)
        main_layout.addWidget(export_tracks_btn)
        main_layout.addWidget(self.params_widget)
        self.setLayout(main_layout)

    def update_run(self, run: MotileRun):
        print(f"Updating run with params {run.solver_params}")
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
    
    def save_run(self):
        if self.save_run_dialog.exec_():
            directory = self.save_run_dialog.selectedFiles()[0]
            print(directory)
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

