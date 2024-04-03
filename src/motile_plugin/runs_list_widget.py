from pathlib import Path

from qtpy.QtCore import Signal, QSize
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QLabel,
)
from napari._qt.qt_resources import QColoredSVGIcon

from .motile_run import MotileRun
from functools import partial


class RunButton(QWidget):
    # https://doc.qt.io/qt-5/qlistwidget.html#setItemWidget
    # I think this means if we want static buttons we can just make the row here
    # but if we want to change the buttons we need to do something more complex
    # Lets start with static then!
    # Columns: Run name, Date/time, new edit config btn, delete btn
    def __init__(self, run):
        super().__init__()
        self.run: MotileRun = run
        self.run_name = QLabel(self.run.run_name)
        self.run_name.setFixedHeight(20)
        self.datetime = QLabel(self.run.time.strftime("%m/%d/%y, %H:%M:%S"))
        self.datetime.setFixedHeight(20)
        self.new_config = QPushButton("+")
        self.new_config.setFixedSize(20, 20)
        icon = QColoredSVGIcon.from_resources("delete")
        self.delete = QPushButton(icon=icon.colored("white"))
        self.delete.setFixedSize(20, 20)
        layout = QHBoxLayout()
        layout.setSpacing(1)
        layout.addWidget(self.run_name)
        layout.addWidget(self.datetime)
        layout.addWidget(self.new_config)
        layout.addWidget(self.delete)
        self.setLayout(layout)
    
    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(30)
        return hint


class RunsList(QWidget):
    """
    For Runs, a couple options:
    - view (read-only)
    - load config (and input seg?) to current run (e.g. New run from loaded run)
    - delete
    - save?
    """

    # TODO: remove storage and loading from widget
    # TODO: Add delete button
    # TODO: Add new config from run button
    view_run = Signal(MotileRun)
    edit_run = Signal(object)

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
        edit_run_button.clicked.connect(partial(self.edit_run.emit, None))
        layout.addWidget(edit_run_button)
        self.setLayout(layout)


    def _load_runs(self):
        return [MotileRun.load(dir) for dir in self.storage_path.iterdir()]

    def _ui_save_load(self):
        save_load_group = QGroupBox("Tracking Runs")
        save_load_layout = QVBoxLayout()
        self.runs_list = QListWidget()
        # self.runs_list.setSpacing(0)
        self.runs_list.setSelectionMode(1)  # single selection
        self.runs_list.itemClicked.connect(
            lambda e: self.view_run.emit(self.runs_list.itemWidget(e).run)
        )
        save_load_layout.addWidget(self.runs_list)

        save_load_group.setLayout(save_load_layout)
        return save_load_group

    def add_run(self, run: MotileRun):
        item = QListWidgetItem(self.runs_list)
        run_row = RunButton(run)
        print(run_row.sizeHint())
        self.runs_list.setItemWidget(item, run_row)
        item.setSizeHint(run_row.minimumSizeHint())
        self.runs_list.addItem(item)
        run_row.delete.clicked.connect(
            partial(self.remove_run, item))
        run_row.new_config.clicked.connect(
            partial(self.edit_run.emit, run)
        )
    
    def save_run(self, run: MotileRun):
        run.save(self.storage_path)

    def remove_run(self, item: QListWidgetItem):
        row = self.runs_list.indexFromItem(item).row()
        run_widget = self.runs_list.itemWidget(item)
        self.runs_list.takeItem(row)
        run_widget.run.delete(self.storage_path)

