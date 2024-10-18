from functools import partial
from pathlib import Path
from warnings import warn

import napari
from fonticon_fa6 import FA6S
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
from superqt.fonticon import icon as qticon

from motile_plugin.data_model import Tracks
from motile_plugin.motile.backend.motile_run import MotileRun


class TrackListWidget(QWidget):
    """Creates or finds a TracksViewer and displays its TrackList widget. This is only used in case the user wants to open the trackslist from the plugins menu."""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        from motile_plugin.data_views.views_coordinator.tracks_viewer import (
            TracksViewer,
        )

        tracks_viewer = TracksViewer.get_instance(viewer)
        layout = QVBoxLayout()
        layout.addWidget(tracks_viewer.tracks_list)

        self.setLayout(layout)


class TracksButton(QWidget):
    # https://doc.qt.io/qt-5/qlistwidget.html#setItemWidget
    # I think this means if we want static buttons we can just make the row here
    # but if we want to change the buttons we need to do something more complex
    # Columns: Run name, Date/time, delete btn
    def __init__(self, tracks: Tracks, name: str):
        super().__init__()
        self.tracks = tracks
        self.name = QLabel(name)
        self.name.setFixedHeight(20)
        delete_icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.delete = QPushButton(icon=delete_icon)
        self.delete.setFixedSize(20, 20)
        save_icon = qticon(FA6S.floppy_disk, color="white")
        self.save = QPushButton(icon=save_icon)
        self.save.setFixedSize(20, 20)
        layout = QHBoxLayout()
        layout.setSpacing(1)
        layout.addWidget(self.name)
        layout.addWidget(self.save)
        layout.addWidget(self.delete)
        self.setLayout(layout)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(30)
        return hint


class TracksList(QGroupBox):
    """Widget for holding in-memory Tracks. Emits a view_tracks signal whenever
    a run is selected in the list, useful for telling the TracksViewer to display the
    selected tracks.
    """

    view_tracks = Signal(Tracks, str)

    def __init__(self):
        super().__init__(title="Results List")
        self.file_dialog = QFileDialog()
        self.file_dialog.setFileMode(QFileDialog.Directory)
        self.file_dialog.setOption(QFileDialog.ShowDirsOnly, True)

        self.save_dialog = QFileDialog()
        self.save_dialog.setFileMode(QFileDialog.Directory)
        self.save_dialog.setOption(QFileDialog.ShowDirsOnly, True)

        self.tracks_list = QListWidget()
        self.tracks_list.setSelectionMode(1)  # single selection
        self.tracks_list.itemSelectionChanged.connect(self._selection_changed)

        load_button = QPushButton("Load tracks")
        load_button.clicked.connect(self.load_tracks)

        layout = QVBoxLayout()
        layout.addWidget(self.tracks_list)
        layout.addWidget(load_button)
        self.setLayout(layout)

    def _selection_changed(self):
        selected = self.tracks_list.selectedItems()
        if selected:
            tracks_button = self.tracks_list.itemWidget(selected[0])
            self.view_tracks.emit(tracks_button.tracks, tracks_button.name.text())

    def add_tracks(self, tracks: Tracks, name: str, select=True):
        """Add a run to the list and optionally select it. Will make a new
        row in the list UI representing the given run.

        Note: selecting the run will also emit the selection changed event on
        the list.

        Args:
            tracks (Tracks): _description_
            select (bool, optional): _description_. Defaults to True.
        """
        item = QListWidgetItem(self.tracks_list)
        tracks_row = TracksButton(tracks, name)
        self.tracks_list.setItemWidget(item, tracks_row)
        item.setSizeHint(tracks_row.minimumSizeHint())
        self.tracks_list.addItem(item)
        tracks_row.delete.clicked.connect(partial(self.remove_tracks, item))
        tracks_row.save.clicked.connect(partial(self.save_tracks, item))
        if select:
            self.tracks_list.setCurrentRow(len(self.tracks_list) - 1)

    def save_tracks(self, item: QListWidgetItem):
        """Saves a tracks object from the list. You must pass the list item that
        represents the tracks, not the tracks object itself.

        Args:
            item (QListWidgetItem): The list item to save. This list item
                contains the TracksButton that represents a set of tracks.
        """
        tracks: Tracks = self.tracks_list.itemWidget(item).tracks
        if self.save_dialog.exec_():
            directory = Path(self.save_dialog.selectedFiles()[0])
            tracks.save(directory)

    def remove_tracks(self, item: QListWidgetItem):
        """Remove a tracks object from the list. You must pass the list item that
        represents the tracks, not the tracks object itself.

        Args:
            item (QListWidgetItem): The list item to remove. This list item
                contains the TracksButton that represents a set of tracks.
        """
        row = self.tracks_list.indexFromItem(item).row()
        self.tracks_list.takeItem(row)

    def load_tracks(self):
        """Load a set of tracks from disk. The user selects the directory created
        by calling save_tracks.
        """
        if self.file_dialog.exec_():
            directory = Path(self.file_dialog.selectedFiles()[0])
            name = directory.stem
            try:
                tracks = MotileRun.load(directory)
                self.add_tracks(tracks, name, select=True)
            except (ValueError, FileNotFoundError):
                try:
                    tracks = Tracks.load(directory)
                    self.add_tracks(tracks, name, select=True)
                except (ValueError, FileNotFoundError) as e:
                    warn(f"Could not load tracks from {directory}: {e}", stacklevel=2)
