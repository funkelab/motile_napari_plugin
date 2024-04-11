
from qtpy.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)
from .solver_params import SolverParamsWidget
from motile_plugin.backend.motile_run import MotileRun
from motile_plugin.backend.solver_params import SolverParams

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
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.run_name_widget)
        self.main_layout.addWidget(self.params_widget)
        self.setLayout(self.main_layout)

    def update_run(self, run: MotileRun):
        print(f"Updating run with params {run.solver_params}")
        self.run = run
        self.run_name_widget.setText(self._run_name_view(self.run))
        self.params_widget.new_params.emit(run.solver_params)

    def _run_name_view(self, run: MotileRun) -> str:
        run_time = run.time.strftime('%m/%d/%y, %H:%M:%S')
        return f"Viewing {run.run_name} ({run_time})"