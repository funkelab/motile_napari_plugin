
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
        
        self.file_dialog = QFileDialog()
        self.file_dialog.setFileMode(QFileDialog.Directory)
        self.file_dialog.setOption(QFileDialog.ShowDirsOnly, True)

        title_widget = QWidget()
        title_layout = QHBoxLayout()
        title_layout.addWidget(self.run_name_widget)
        title_layout.addWidget(self._save_widget())
        title_widget.setLayout(title_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(title_widget)
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
        if self.file_dialog.exec_():
            directory = self.file_dialog.selectedFiles()[0]
            print(directory)
            self.run.save(directory)
        else:
            warn("Saving aborted")