from functools import partial
from warnings import warn

from napari._qt.qt_resources import QColoredSVGIcon
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from motile_plugin.backend.motile_run import MotileRun


class RunButton(QWidget):
    # https://doc.qt.io/qt-5/qlistwidget.html#setItemWidget
    # I think this means if we want static buttons we can just make the row here
    # but if we want to change the buttons we need to do something more complex
    # Columns: Run name, Date/time, delete btn
    def __init__(self, run: MotileRun):
        super().__init__()
        self.run = run
        self.run_name = QLabel(self.run.run_name)
        self.run_name.setFixedHeight(20)
        self.datetime = QLabel(self.run.time.strftime("%m/%d/%y, %H:%M:%S"))
        self.datetime.setFixedHeight(20)
        icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.delete = QPushButton(icon=icon)
        self.delete.setFixedSize(20, 20)
        layout = QHBoxLayout()
        layout.setSpacing(1)
        layout.addWidget(self.run_name)
        layout.addWidget(self.datetime)
        layout.addWidget(self.delete)
        self.setLayout(layout)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(30)
        return hint


class RunsList(QGroupBox):
    """Widget for holding in-memory Runs. Emits a view_run signal whenever
    a run is selected in the list, useful for telling the widget to display the
    selected run.
    """

    view_run = Signal(MotileRun)

    def __init__(self):
        super().__init__(title="Tracking Runs")
        self.file_dialog = QFileDialog()
        self.file_dialog.setFileMode(QFileDialog.Directory)
        self.file_dialog.setOption(QFileDialog.ShowDirsOnly, True)

        self.runs_list = QListWidget()
        self.runs_list.setSelectionMode(1)  # single selection
        self.runs_list.itemSelectionChanged.connect(self._selection_changed)

        load_button = QPushButton("Load run")
        load_button.clicked.connect(self.load_run)

        layout = QVBoxLayout()
        layout.addWidget(self.runs_list)
        layout.addWidget(load_button)
        self.setLayout(layout)

    def _selection_changed(self):
        selected = self.runs_list.selectedItems()
        if selected:
            self.view_run.emit(self.runs_list.itemWidget(selected[0]).run)

    def add_run(self, run: MotileRun, select=True):
        """Add a run to the list and optionally select it. Will make a new
        row in the list UI representing the given run.

        Note: selecting the run will also emit the selection changed event on
        the list.

        Args:
            run (MotileRun): _description_
            select (bool, optional): _description_. Defaults to True.
        """
        item = QListWidgetItem(self.runs_list)
        run_row = RunButton(run)
        self.runs_list.setItemWidget(item, run_row)
        item.setSizeHint(run_row.minimumSizeHint())
        self.runs_list.addItem(item)
        run_row.delete.clicked.connect(partial(self.remove_run, item))
        if select:
            self.runs_list.setCurrentRow(len(self.runs_list) - 1)

    def remove_run(self, item: QListWidgetItem):
        """Remove a run from the list. You must pass the list item that
        represents the run, not the run itself.

        Args:
            item (QListWidgetItem): The list item to remove. This list item
                contains the RunButton that represents a run.
        """
        row = self.runs_list.indexFromItem(item).row()
        self.runs_list.takeItem(row)

    def load_run(self):
        """Load a run from disk. The user selects the run directory created
        by calling save_run (named with the timestamp and run name).
        """
        if self.file_dialog.exec_():
            directory = self.file_dialog.selectedFiles()[0]
            try:
                run = MotileRun.load(directory)
                self.add_run(run, select=True)
            except (ValueError, FileNotFoundError) as e:
                warn(f"Could not load run from {directory}: {e}", stacklevel=2)
