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

from motile_plugin.backend.motile_run import MotileRun
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
    """Widget for holding in-memory Runs
    """
    view_run = Signal(MotileRun)
    edit_run = Signal(object)

    def __init__(self):
        super().__init__()
        self.runs_list: QListWidget

        layout = QVBoxLayout()
        layout.addWidget(self._ui_save_load())

        self.edit_run_button = QPushButton("Back to Editing")
        self.edit_run_button.clicked.connect(partial(self.edit_run.emit, None))
        self.edit_run_button.clicked.connect(self.runs_list.clearSelection)
        layout.addWidget(self.edit_run_button)
        self.setLayout(layout)

    def _view_run(self, e):
        self.view_run.emit(self.runs_list.itemWidget(e).run)
        self.edit_run_button.show()

    def _ui_save_load(self):
        save_load_group = QGroupBox("Tracking Runs")
        save_load_layout = QVBoxLayout()
        self.runs_list = QListWidget()
        # self.runs_list.setSpacing(0)
        self.runs_list.setSelectionMode(1)  # single selection
        self.runs_list.itemClicked.connect(self._view_run)
        save_load_layout.addWidget(self.runs_list)
        save_load_group.setLayout(save_load_layout)
        return save_load_group

    def add_run(self, run: MotileRun, select=True):
        item = QListWidgetItem(self.runs_list)
        run_row = RunButton(run)
        self.runs_list.setItemWidget(item, run_row)
        item.setSizeHint(run_row.minimumSizeHint())
        self.runs_list.addItem(item)
        run_row.delete.clicked.connect(
            partial(self.remove_run, item))
        run_row.new_config.clicked.connect(
            partial(self.edit_run.emit, run)  # Note: this may cause memory leak
            # Can use weakref if that happens
            # https://github.com/Carreau/napari/commit/cd079e9dcb62de115833ea1b6bb1b7a0ab4b78d1
        )
        if select:
            self.runs_list.setCurrentRow(-1)

    def remove_run(self, item: QListWidgetItem):
        row = self.runs_list.indexFromItem(item).row()
        self.runs_list.takeItem(row)

