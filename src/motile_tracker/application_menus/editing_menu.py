import napari
from qtpy.QtWidgets import (
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


class EditingMenu(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.selected_nodes.list_updated.connect(self.update_buttons)
        layout = QVBoxLayout()

        node_box = QGroupBox("Edit Node(s)")
        node_box.setMaximumHeight(60)
        node_box_layout = QVBoxLayout()

        self.delete_node_btn = QPushButton("Delete [D]")
        self.delete_node_btn.clicked.connect(self.tracks_viewer.delete_node)
        self.delete_node_btn.setEnabled(False)
        # self.split_node_btn = QPushButton("Set split [S]")
        # self.split_node_btn.clicked.connect(self.tracks_viewer.set_split_node)
        # self.split_node_btn.setEnabled(False)
        # self.endpoint_node_btn = QPushButton("Set endpoint [E]")
        # self.endpoint_node_btn.clicked.connect(self.tracks_viewer.set_endpoint_node)
        # self.endpoint_node_btn.setEnabled(False)
        # self.linear_node_btn = QPushButton("Set linear [C]")
        # self.linear_node_btn.clicked.connect(self.tracks_viewer.set_linear_node)
        # self.linear_node_btn.setEnabled(False)

        node_box_layout.addWidget(self.delete_node_btn)
        # node_box_layout.addWidget(self.split_node_btn)
        # node_box_layout.addWidget(self.endpoint_node_btn)
        # node_box_layout.addWidget(self.linear_node_btn)

        node_box.setLayout(node_box_layout)

        edge_box = QGroupBox("Edit Edge(s)")
        edge_box.setMaximumHeight(100)
        edge_box_layout = QVBoxLayout()

        self.delete_edge_btn = QPushButton("Break [B]")
        self.delete_edge_btn.clicked.connect(self.tracks_viewer.delete_edge)
        self.delete_edge_btn.setEnabled(False)
        self.create_edge_btn = QPushButton("Add [A]")
        self.create_edge_btn.clicked.connect(self.tracks_viewer.create_edge)
        self.create_edge_btn.setEnabled(False)

        edge_box_layout.addWidget(self.delete_edge_btn)
        edge_box_layout.addWidget(self.create_edge_btn)

        edge_box.setLayout(edge_box_layout)

        self.undo_btn = QPushButton("Undo (Z)")
        self.undo_btn.clicked.connect(self.tracks_viewer.undo)

        self.redo_btn = QPushButton("Redo (R)")
        self.redo_btn.clicked.connect(self.tracks_viewer.redo)

        layout.addWidget(node_box)
        layout.addWidget(edge_box)
        layout.addWidget(self.undo_btn)
        layout.addWidget(self.redo_btn)

        self.setLayout(layout)
        self.setMaximumHeight(300)

    def update_buttons(self):
        """Set the buttons to enabled/disabled depending on the currently selected nodes"""

        n_selected = len(self.tracks_viewer.selected_nodes)
        if n_selected == 0:
            self.delete_node_btn.setEnabled(False)
            # self.split_node_btn.setEnabled(False)
            # self.endpoint_node_btn.setEnabled(False)
            # self.linear_node_btn.setEnabled(False)
            self.delete_edge_btn.setEnabled(False)
            self.create_edge_btn.setEnabled(False)

        elif n_selected == 2:
            self.delete_node_btn.setEnabled(True)
            # self.split_node_btn.setEnabled(True)
            # self.endpoint_node_btn.setEnabled(True)
            # self.linear_node_btn.setEnabled(True)
            self.delete_edge_btn.setEnabled(True)
            self.create_edge_btn.setEnabled(True)

        else:
            self.delete_node_btn.setEnabled(True)
            # self.split_node_btn.setEnabled(True)
            # self.endpoint_node_btn.setEnabled(True)
            # self.linear_node_btn.setEnabled(True)
            self.delete_edge_btn.setEnabled(False)
            self.create_edge_btn.setEnabled(False)
