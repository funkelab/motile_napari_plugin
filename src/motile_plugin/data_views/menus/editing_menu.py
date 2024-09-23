import napari
import numpy as np
from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer
from qtpy.QtWidgets import (
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class EditingMenu(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.tracks_viewer.selected_nodes.list_updated.connect(self.update_buttons)
        layout = QVBoxLayout()

        node_box = QGroupBox("Edit Node(s)")
        node_box_layout = QVBoxLayout()

        self.delete_node_btn = QPushButton("Delete")
        self.delete_node_btn.clicked.connect(self.delete_node)
        self.delete_node_btn.setEnabled(False)
        self.split_node_btn = QPushButton("Set split")
        self.split_node_btn.clicked.connect(self.set_split_node)
        self.split_node_btn.setEnabled(False)
        self.endpoint_node_btn = QPushButton("Set endpoint")
        self.endpoint_node_btn.clicked.connect(self.set_endpoint_node)
        self.endpoint_node_btn.setEnabled(False)
        self.linear_node_btn = QPushButton("Set linear")
        self.linear_node_btn.clicked.connect(self.set_linear_node)
        self.linear_node_btn.setEnabled(False)

        node_box_layout.addWidget(self.delete_node_btn)
        node_box_layout.addWidget(self.split_node_btn)
        node_box_layout.addWidget(self.endpoint_node_btn)
        node_box_layout.addWidget(self.linear_node_btn)

        node_box.setLayout(node_box_layout)

        edge_box = QGroupBox("Edit Edge(s)")
        edge_box_layout = QVBoxLayout()

        self.delete_edge_btn = QPushButton("Delete")
        self.delete_edge_btn.clicked.connect(self.delete_edge)
        self.delete_edge_btn.setEnabled(False)
        self.create_edge_btn = QPushButton("Create")
        self.create_edge_btn.clicked.connect(self.create_edge)
        self.create_edge_btn.setEnabled(False)

        edge_box_layout.addWidget(self.delete_edge_btn)
        edge_box_layout.addWidget(self.create_edge_btn)

        edge_box.setLayout(edge_box_layout)

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo)

        layout.addWidget(node_box)
        layout.addWidget(edge_box)
        layout.addWidget(self.undo_btn)

        self.setLayout(layout)

    def update_buttons(self):
        """Set the buttons to enabled/disabled depending on the currently selected nodes"""

        n_selected = len(self.tracks_viewer.selected_nodes)
        if n_selected == 0:
            self.delete_node_btn.setEnabled(False)
            self.split_node_btn.setEnabled(False)
            self.endpoint_node_btn.setEnabled(False)
            self.linear_node_btn.setEnabled(False)
            self.delete_edge_btn.setEnabled(False)
            self.create_edge_btn.setEnabled(False)

        elif n_selected == 2:
            self.delete_node_btn.setEnabled(True)
            self.split_node_btn.setEnabled(True)
            self.endpoint_node_btn.setEnabled(True)
            self.linear_node_btn.setEnabled(True)
            self.delete_edge_btn.setEnabled(True)
            self.create_edge_btn.setEnabled(True)

        else:
            self.delete_node_btn.setEnabled(True)
            self.split_node_btn.setEnabled(True)
            self.endpoint_node_btn.setEnabled(True)
            self.linear_node_btn.setEnabled(True)
            self.delete_edge_btn.setEnabled(False)
            self.create_edge_btn.setEnabled(False)

    def delete_node(self):
        """Calls the tracks controller to delete currently selected nodes"""

        self.tracks_viewer.tracks_controller.delete_nodes(
            np.array(self.tracks_viewer.selected_nodes._list)
        )

    def set_split_node(self):
        print("split this node")

    def set_endpoint_node(self):
        print("make this node an endpoint")

    def set_linear_node(self):
        print("make this node linear")

    def delete_edge(self):
        """Calls the tracks controller to delete an edge between the two currently selected nodes"""

        node1 = self.tracks_viewer.selected_nodes[0]
        node2 = self.tracks_viewer.selected_nodes[1]

        time1 = self.tracks_viewer.tracks.get_time(node1)
        time2 = self.tracks_viewer.tracks.get_time(node2)

        if time1 > time2:
            node1, node2 = node2, node1

        self.tracks_viewer.tracks_controller.delete_edges(
            edges=np.array([[node1, node2]])
        )

    def create_edge(self):
        """Calls the tracks controller to add an edge between the two currently selected nodes"""

        node1 = self.tracks_viewer.selected_nodes[0]
        node2 = self.tracks_viewer.selected_nodes[1]

        time1 = self.tracks_viewer.tracks.get_time(node1)
        time2 = self.tracks_viewer.tracks.get_time(node2)

        if time1 > time2:
            node1, node2 = node2, node1

        self.tracks_viewer.tracks_controller.add_edges(
            edges=np.array([[node1, node2]]), attributes={}
        )

    def undo(self):
        controller = self.tracks_viewer.tracks_controller
        action_to_undo = controller.actions[controller.last_action]
        self.tracks_viewer.tracks_controller.last_action -= 1
        inverse_action = action_to_undo.inverse()
        print(inverse_action)
        inverse_action.apply()
        self.tracks_viewer.tracks.refresh()

    def redo(self):
        controller = self.tracks_viewer.tracks_controller
        if controller.last_action < len(controller.actions) - 1:
            action_to_redo = controller.actions[controller.last_action + 1]
            self.tracks_viewer.tracks_controller.last_action += 1
            action_to_redo.apply()
            self.tracks_viewer.tracks.refresh()
