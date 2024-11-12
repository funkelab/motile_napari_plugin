import napari
from qtpy.QtWidgets import QScrollArea, QTabWidget, QVBoxLayout

from motile_plugin.application_menus.editing_menu import EditingMenu
from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_plugin.motile.menus.motile_widget import MotileWidget


class MenuWidget(QScrollArea):
    """Combines the different plugin menus into tabs for cleaner UI"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        tracks_viewer = TracksViewer.get_instance(viewer)

        motile_widget = MotileWidget(viewer)
        editing_widget = EditingMenu(viewer)

        tabwidget = QTabWidget()

        tabwidget.addTab(motile_widget, "Track with Motile")
        tabwidget.addTab(editing_widget, "Edit Tracks")
        tabwidget.addTab(tracks_viewer.tracks_list, "Results List")
        tabwidget.addTab(tracks_viewer.collection_widget, "Collections")
        tabwidget.addTab(tracks_viewer.filter_widget, "Filters")

        layout = QVBoxLayout()
        layout.addWidget(tabwidget)

        self.setWidget(tabwidget)
        self.setWidgetResizable(True)

        self.setLayout(layout)
