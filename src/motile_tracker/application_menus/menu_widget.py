import napari
from qtpy.QtWidgets import QScrollArea, QTabWidget, QVBoxLayout

from motile_tracker.application_menus.editing_menu import EditingMenu
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.motile.menus.motile_widget import MotileWidget


class MenuWidget(QScrollArea):
    """Combines the different tracker menus into tabs for cleaner UI"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        tracks_viewer = TracksViewer.get_instance(viewer)

        motile_widget = MotileWidget(viewer)
        editing_widget = EditingMenu(viewer)

        tabwidget = QTabWidget()

        tabwidget.addTab(motile_widget, "Track with Motile")
        tabwidget.addTab(editing_widget, "Edit Tracks")
        tabwidget.addTab(tracks_viewer.tracks_list, "Results List")

        layout = QVBoxLayout()
        layout.addWidget(tabwidget)

        self.setWidget(tabwidget)
        self.setWidgetResizable(True)

        self.setLayout(layout)
