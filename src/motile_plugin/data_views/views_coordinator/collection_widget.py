from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from motile_toolbox.candidate_graph.graph_attributes import NodeAttr
from napari._qt.qt_resources import QColoredSVGIcon
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from motile_plugin.data_views.views.tree_view.tree_widget_utils import (
    extract_lineage_tree,
)

from . import Collection

if TYPE_CHECKING:
    from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer


class CollectionButton(QWidget):
    """Widget holding a name and delete icon for listing in the QListWidget. Also contains an initially empty instance of a Collection to which nodes can be assigned"""

    def __init__(self, name: str):
        super().__init__()
        self.name = QLabel(name)
        self.name.setFixedHeight(20)
        self.collection = Collection()
        delete_icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.delete = QPushButton(icon=delete_icon)
        self.delete.setFixedSize(20, 20)
        layout = QHBoxLayout()
        layout.setSpacing(1)
        layout.addWidget(self.name)
        layout.addWidget(self.delete)
        self.setLayout(layout)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(30)
        return hint


class CollectionWidget(QGroupBox):
    """Widget for holding in-memory Collections (groups). Emits a signal whenever
    a collection is selected in the list, to update the viewing properties
    """

    group_changed = Signal()

    def __init__(self, tracks_viewer: TracksViewer):
        super().__init__(title="Collections")

        self.tracks_viewer = tracks_viewer

        self.collection_list = QListWidget()
        self.collection_list.setSelectionMode(1)  # single selection
        self.collection_list.itemSelectionChanged.connect(self._selection_changed)
        self.selected_collection = None

        # edit layout
        edit_widget = QGroupBox("Edit")
        edit_layout = QVBoxLayout()

        add_layout = QHBoxLayout()
        add_node = QPushButton("Add node(s)")
        add_node.clicked.connect(self.add_node)
        add_track = QPushButton("Add track(s)")
        add_track.clicked.connect(self.add_track)
        add_lineage = QPushButton("Add lineage(s)")
        add_lineage.clicked.connect(self.add_lineage)
        add_layout.addWidget(add_node)
        add_layout.addWidget(add_track)
        add_layout.addWidget(add_lineage)

        remove_layout = QHBoxLayout()
        remove_node = QPushButton("Remove node(s)")
        remove_node.clicked.connect(self.remove_node)
        remove_track = QPushButton("Remove track(s)")
        remove_track.clicked.connect(self.remove_track)
        remove_lineage = QPushButton("Remove lineage(s)")
        remove_lineage.clicked.connect(self.remove_lineage)
        remove_layout.addWidget(remove_node)
        remove_layout.addWidget(remove_track)
        remove_layout.addWidget(remove_lineage)

        edit_layout.addLayout(add_layout)
        edit_layout.addLayout(remove_layout)
        edit_widget.setLayout(edit_layout)

        # adding a new group
        new_group_layout = QHBoxLayout()
        new_group_layout.addWidget(QLabel("New group:"))
        self.group_name = QLineEdit("new group")
        new_group_layout.addWidget(self.group_name)
        new_group_button = QPushButton("Create")
        new_group_button.clicked.connect(self.new_group)
        new_group_layout.addWidget(new_group_button)

        # combine widgets
        layout = QVBoxLayout()
        layout.addWidget(self.collection_list)
        layout.addWidget(edit_widget)
        layout.addLayout(new_group_layout)
        self.setLayout(layout)

    def retrieve_existing_groups(self):
        """Create collections based on the node attributes. Nodes assigned to a group should have that group in their 'group' attribute"""

        # first clear the entire list
        self.collection_list.clear()

        # check for existing groups in the node attributes
        group_dict = {}
        for node, data in self.tracks_viewer.tracks.graph.nodes(data=True):
            groups = data.get("group")
            if groups:  # Only add if 'group' attribute is present and not None
                for group in groups:
                    if group not in group_dict:
                        group_dict[group] = []
                        self.add_group(group, select=False)
                    group_dict[group].append(node)

        # populate the lists based on the nodes that were assigned to the different groups
        for i in range(self.collection_list.count()):
            self.collection_list.setCurrentRow(i)
            self.selected_collection.collection.add(
                group_dict[self.selected_collection.name.text()]
            )

    def _selection_changed(self):
        """Update the currently selected collection and send update signal"""

        selected = self.collection_list.selectedItems()
        if selected:
            self.selected_collection = self.collection_list.itemWidget(selected[0])
            self.group_changed.emit()

    def add_node(self):
        """Add individual nodes to the selected collection and send update signal"""

        if self.selected_collection is not None:
            self.selected_collection.collection.add(self.tracks_viewer.selected_nodes)
            for node_id in self.tracks_viewer.selected_nodes:
                if "group" not in self.tracks_viewer.tracks.graph.nodes[node_id]:
                    self.tracks_viewer.tracks.graph.nodes[node_id]["group"] = []
                if (
                    self.selected_collection.name.text()
                    not in self.tracks_viewer.tracks.graph.nodes[node_id]["group"]
                ):
                    self.tracks_viewer.tracks.graph.nodes[node_id]["group"].append(
                        self.selected_collection.name.text()
                    )
            self.group_changed.emit()

    def add_track(self):
        """Add tracks by track_ids to the selected collection and send update signal"""

        if self.selected_collection is not None:
            for node_id in self.tracks_viewer.selected_nodes:
                track_id = self.tracks_viewer.tracks._get_node_attr(
                    node_id, NodeAttr.TRACK_ID.value
                )
                track = list(
                    {
                        node
                        for node, data in self.tracks_viewer.tracks.graph.nodes(
                            data=True
                        )
                        if data.get("track_id") == track_id
                    }
                )
                self.selected_collection.collection.add(track)
                for node_id in track:
                    if "group" not in self.tracks_viewer.tracks.graph.nodes[node_id]:
                        self.tracks_viewer.tracks.graph.nodes[node_id]["group"] = []
                    if (
                        self.selected_collection.name.text()
                        not in self.tracks_viewer.tracks.graph.nodes[node_id]["group"]
                    ):
                        self.tracks_viewer.tracks.graph.nodes[node_id]["group"].append(
                            self.selected_collection.name.text()
                        )
            self.group_changed.emit()

    def add_lineage(self):
        """Add lineages to the selected collection and send update signal"""

        if self.selected_collection is not None:
            for node_id in self.tracks_viewer.selected_nodes:
                lineage = extract_lineage_tree(self.tracks_viewer.tracks.graph, node_id)
                self.selected_collection.collection.add(lineage)
                for node_id in lineage:
                    if "group" not in self.tracks_viewer.tracks.graph.nodes[node_id]:
                        self.tracks_viewer.tracks.graph.nodes[node_id]["group"] = []
                    if (
                        self.selected_collection.name.text()
                        not in self.tracks_viewer.tracks.graph.nodes[node_id]["group"]
                    ):
                        self.tracks_viewer.tracks.graph.nodes[node_id]["group"].append(
                            self.selected_collection.name.text()
                        )
            self.group_changed.emit()

    def remove_node(self):
        """Remove individual nodes from the selected collection and send update signal"""

        if self.selected_collection is not None:
            self.selected_collection.collection.remove(
                self.tracks_viewer.selected_nodes
            )
            for node_id in self.tracks_viewer.selected_nodes:
                self.tracks_viewer.tracks.graph.nodes[node_id]["group"].remove(
                    self.selected_collection.name.text()
                )
            self.group_changed.emit()

    def remove_track(self):
        """Remove tracks by track id from the selected collection and send update signal"""

        if self.selected_collection is not None:
            for node_id in self.tracks_viewer.selected_nodes:
                track_id = self.tracks_viewer.tracks._get_node_attr(
                    node_id, NodeAttr.TRACK_ID.value
                )
                track = list(
                    {
                        node
                        for node, data in self.tracks_viewer.tracks.graph.nodes(
                            data=True
                        )
                        if data.get("track_id") == track_id
                    }
                )
                self.selected_collection.collection.remove(track)
                for node_id in track:
                    self.tracks_viewer.tracks.graph.nodes[node_id]["group"].remove(
                        self.selected_collection.name.text()
                    )
        self.group_changed.emit()

    def remove_lineage(self):
        """Remove lineages from the selected collection and send update signal"""

        if self.selected_collection is not None:
            for node_id in self.tracks_viewer.selected_nodes:
                lineage = extract_lineage_tree(self.tracks_viewer.tracks.graph, node_id)
                self.selected_collection.collection.remove(lineage)
                for node_id in lineage:
                    self.tracks_viewer.tracks.graph.nodes[node_id]["group"].remove(
                        self.selected_collection.name.text()
                    )
        self.group_changed.emit()

    def add_group(self, name: str, select=True):
        """Create a new custom group"""

        names = [
            self.collection_list.itemWidget(self.collection_list.item(i)).name.text()
            for i in range(self.collection_list.count())
        ]
        while name in names:
            name = name + "_1"
        item = QListWidgetItem(self.collection_list)
        group_row = CollectionButton(name)
        self.collection_list.setItemWidget(item, group_row)
        item.setSizeHint(group_row.minimumSizeHint())
        self.collection_list.addItem(item)
        group_row.delete.clicked.connect(partial(self.remove_group, item))
        if select:
            self.collection_list.setCurrentRow(len(self.collection_list) - 1)

    def remove_group(self, item: QListWidgetItem):
        """Remove a collection object from the list. You must pass the list item that
        represents the collection, not the collection object itself.

        Args:
            item (QListWidgetItem): The list item to remove. This list item
                contains the CollectionButton that represents a set of node_ids.
        """
        row = self.collection_list.indexFromItem(item).row()
        group_name = self.collection_list.itemWidget(item).name.text()
        self.collection_list.takeItem(row)

        # also delete the group from the node attributes
        for _, data in self.tracks_viewer.tracks.graph.nodes(data=True):
            groups = data.get("group")

            if groups and group_name in groups:
                groups.remove(group_name)  # Remove the group from the list

    def new_group(self):
        """Create a new group"""

        self.add_group(name=self.group_name.text(), select=True)
