import napari
from motile_plugin.data_views.menus.editing_menu import EditingMenu
from motile_plugin.data_views.views.tree_view.tree_widget import TreeWidget
from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_plugin.motile.menus.motile_widget import MotileWidget
from qtpy.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class MultiWidget(QWidget):
    """Combines the different plugin widgets for faster dock arrangement"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        tracks_viewer = TracksViewer.get_instance(viewer)

        motile_widget = MotileWidget(viewer)
        editing_widget = EditingMenu(viewer)
        tree_widget = TreeWidget(viewer)

        tabwidget = QTabWidget()

        tabwidget.addTab(motile_widget, "Motile")
        tabwidget.addTab(editing_widget, "Edit Tracks")
        tabwidget.addTab(tracks_viewer.tracks_list, "Track List")

        viewer.window.add_dock_widget(tree_widget, area="bottom", name="Tree View")

        layout = QVBoxLayout()
        layout.addWidget(tabwidget)

        self.setLayout(layout)
