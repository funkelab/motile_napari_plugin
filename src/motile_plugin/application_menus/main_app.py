import napari
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from motile_plugin.data_views.views.tree_view.tree_widget import TreeWidget

from .menu_widget import MenuWidget


class MainApp(QWidget):
    """Combines the different plugin widgets for faster dock arrangement"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        menu_widget = MenuWidget(viewer)
        tree_widget = TreeWidget(viewer)

        viewer.window.add_dock_widget(tree_widget, area="bottom", name="Tree View")

        layout = QVBoxLayout()
        layout.addWidget(menu_widget)

        self.setLayout(layout)
