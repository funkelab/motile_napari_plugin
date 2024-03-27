from pathlib import Path

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .motile_run import MotileRun


class RunButton(QListWidgetItem):
    def __init__(self, run, *args, **kwargs):
        self.run: MotileRun = run
        time_text = run.time.strftime("%m/%d/%Y, %H:%M:%S")
        btn_text = f"{run.run_name} ({time_text})"
        super().__init__(btn_text, *args, **kwargs)

class RunsList(QWidget):
    # TODO: remove storage and loading from widget
    # TODO: Add delete button
    # TODO: Add new config from run button
    view_run = Signal(MotileRun)
    edit_run = Signal()

    def __init__(self, storage_path):
        super().__init__()
        self.runs_list: QListWidget
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        layout = QVBoxLayout()
        layout.addWidget(self._ui_save_load())
        for run in self._load_runs():
            self.add_run(run)

        edit_run_button = QPushButton("Back to Editing")
        edit_run_button.clicked.connect(self.edit_run.emit)
        layout.addWidget(edit_run_button)
        self.setLayout(layout)


    def _load_runs(self):
        return [MotileRun.load(dir) for dir in self.storage_path.iterdir()]

    def _ui_save_load(self):
        save_load_group = QGroupBox("Tracking Runs")
        save_load_layout = QVBoxLayout()
        self.runs_list = QListWidget()
        self.runs_list.setSelectionMode(1)  # single selection
        self.runs_list.itemClicked.connect(
            lambda e: self.view_run.emit(e.run)
        )
        save_load_layout.addWidget(self.runs_list)

        save_load_group.setLayout(save_load_layout)
        return save_load_group

    def add_run(self, run: MotileRun):
        self.runs_list.addItem(RunButton(run))
    
    def save_run(self, run: MotileRun):
        run.save(self.storage_path)

    def remove_run(self, row_index):
        run_button: RunButton = self.runs_list.takeItem(row_index)
        run_button.run.delete(self.storage_path)

