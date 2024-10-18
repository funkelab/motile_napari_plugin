from __future__ import annotations

from typing import Optional

import napari
import numpy as np
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr
from psygnal import Signal

from motile_plugin.data_model import NodeType, SolutionTracks, Tracks
from motile_plugin.data_model.tracks_controller import TracksController
from motile_plugin.data_views.views.layers.tracks_layer_group import TracksLayerGroup
from motile_plugin.data_views.views.tree_view.tree_widget_utils import (
    extract_lineage_tree,
)
from motile_plugin.utils.relabel_segmentation import relabel_segmentation

from .node_selection_list import NodeSelectionList
from .tracks_list import TracksList


class TracksViewer:
    """Purposes of the TracksViewer:
    - Emit signals that all widgets should use to update selection or update
        the currently displayed Tracks object
    - Storing the currently displayed tracks
    - Store shared rendering information like colormaps (or symbol maps)
    """

    tracks_updated = Signal(Optional[bool])

    @classmethod
    def get_instance(cls, viewer=None):
        if not hasattr(cls, "_instance"):
            print("Making new tracking view controller")
            if viewer is None:
                raise ValueError("Make a viewer first please!")
            cls._instance = TracksViewer(viewer)
        return cls._instance

    def __init__(
        self,
        viewer: napari.viewer,
    ):
        self.viewer = viewer
        self.colormap = napari.utils.colormaps.label_colormap(
            49,
            seed=0.5,
            background_value=0,
        )

        self.symbolmap: dict[NodeType, str] = {
            NodeType.END: "x",
            NodeType.CONTINUE: "disc",
            NodeType.SPLIT: "triangle_up",
        }
        self.mode = "all"
        self.tracks = None
        self.visible = None
        self.tracking_layers = TracksLayerGroup(self.viewer, self.tracks, "", self)

        self.selected_nodes = NodeSelectionList()
        self.selected_nodes.list_updated.connect(self.update_selection)

        self.tracks_list = TracksList()
        self.tracks_list.view_tracks.connect(self.update_tracks)

        self.set_keybinds()

    def set_keybinds(self):
        # TODO: separate and document keybinds (and maybe allow user to choose)
        self.viewer.bind_key("q")(self.toggle_display_mode)
        self.viewer.bind_key("a")(self.create_edge)
        self.viewer.bind_key("d")(self.delete_node)
        self.viewer.bind_key("Delete")(self.delete_node)
        self.viewer.bind_key("b")(self.delete_edge)
        # self.viewer.bind_key("s")(self.set_split_node)
        # self.viewer.bind_key("e")(self.set_endpoint_node)
        # self.viewer.bind_key("c")(self.set_linear_node)
        self.viewer.bind_key("z")(self.undo)
        self.viewer.bind_key("r")(self.redo)

    def _refresh(self, node: str | None = None, refresh_view: bool = False) -> None:
        """Call refresh function on napari layers and the submit signal that tracks are updated
        Restore the selected_nodes, if possible
        """

        if len(self.selected_nodes) > 0 and any(
            not self.tracks.graph.has_node(node) for node in self.selected_nodes
        ):
            self.selected_nodes.reset()

        self.tracking_layers._refresh()

        self.tracks_updated.emit(refresh_view)

        # if a new node was added, we would like to select this one now (call this after emitting the signal, because if the node is a new node, we have to update the table in the tree widget first, or it won't be present)
        if node is not None:
            self.selected_nodes.add(node)

        # restore selection and/or highlighting in all napari Views (napari Views do not know about their selection ('all' vs 'lineage'), but TracksViewer does)
        self.update_selection()

    def update_tracks(self, tracks: Tracks, name: str) -> None:
        """Stop viewing a previous set of tracks and replace it with a new one.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            tracks (motile_plugin.core.Tracks): The tracks to visualize in napari.
            name (str): The name of the tracks to display in the layer names
        """
        self.selected_nodes._list = []

        if self.tracks is not None:
            self.tracks.refresh.disconnect(self._refresh)

        self.tracks = tracks
        self.tracks_controller = TracksController(self.tracks)

        # listen to refresh signals from the tracks
        self.tracks.refresh.connect(self._refresh)

        # deactivate the input labels layer
        for layer in self.viewer.layers:
            if isinstance(layer, (napari.layers.Labels | napari.layers.Points)):
                layer.visible = False

        self.set_display_mode("all")
        self.tracking_layers.set_tracks(tracks, name)
        self.selected_nodes.reset()
        self.tracks_updated.emit(True)

    def toggle_display_mode(self, event=None) -> None:
        """Toggle the display mode between available options"""

        if self.mode == "lineage":
            self.set_display_mode("all")
        else:
            self.set_display_mode("lineage")

    def set_display_mode(self, mode: str) -> None:
        """Update the display mode and call to update colormaps for points, labels, and tracks"""

        # toggle between 'all' and 'lineage'
        if mode == "lineage":
            self.mode = "lineage"
            self.viewer.text_overlay.text = "Toggle Display [Q]\n Lineage"
        else:
            self.mode = "all"
            self.viewer.text_overlay.text = "Toggle Display [Q]\n All"

        self.viewer.text_overlay.visible = True
        visible = self.filter_visible_nodes()
        self.tracking_layers.update_visible(visible)

    def filter_visible_nodes(self) -> list[int]:
        """Construct a list of track_ids that should be displayed"""

        if self.tracks is None or self.tracks.graph is None:
            return []
        if self.mode == "lineage":
            # if no nodes are selected, check which nodes were previously visible and filter those
            if len(self.selected_nodes) == 0 and self.visible is not None:
                prev_visible = [
                    node for node in self.visible if self.tracks.graph.has_node(node)
                ]
                self.visible = []
                for node_id in prev_visible:
                    self.visible += extract_lineage_tree(self.tracks.graph, node_id)
                    if set(prev_visible).issubset(self.visible):
                        break
            else:
                self.visible = []
                for node in self.selected_nodes:
                    self.visible += extract_lineage_tree(self.tracks.graph, node)

            return list(
                {
                    self.tracks.graph.nodes[node][NodeAttr.TRACK_ID.value]
                    for node in self.visible
                }
            )
        else:
            return "all"

    def update_selection(self) -> None:
        """Sets the view and triggers visualization updates in other components"""

        self.set_napari_view()
        visible = self.filter_visible_nodes()
        self.tracking_layers.update_visible(visible)

    def view_external_tracks(self, tracks: SolutionTracks, name: str) -> None:
        """View tracks created externally. Assigns tracklet ids, adds a hypothesis
        dimension to the segmentation, and relabels the segmentation based on the
        assigned track ids. Then calls update_tracks.

        Args:
            tracks (Tracks): A tracks object to view, created externally from the plugin
            name (str): The name to display in napari layers
        """
        tracks.segmentation = np.expand_dims(tracks.segmentation, axis=1)
        tracks.segmentation = relabel_segmentation(tracks.graph, tracks.segmentation)
        self.update_tracks(tracks, name)

    def set_napari_view(self) -> None:
        """Adjust the current_step of the viewer to jump to the last item of the selected_nodes list"""
        if len(self.selected_nodes) > 0:
            node = self.selected_nodes[-1]
            self.tracking_layers.center_view(node)

    def delete_node(self, event=None):
        """Calls the tracks controller to delete currently selected nodes"""

        self.tracks_controller.delete_nodes(self.selected_nodes._list)

    def set_split_node(self, event=None):
        print("split this node")

    def set_endpoint_node(self, event=None):
        print("make this node an endpoint")

    def set_linear_node(self, event=None):
        print("make this node linear")

    def delete_edge(self, event=None):
        """Calls the tracks controller to delete an edge between the two currently selected nodes"""

        if len(self.selected_nodes) == 2:
            node1 = self.selected_nodes[0]
            node2 = self.selected_nodes[1]

            time1 = self.tracks.get_time(node1)
            time2 = self.tracks.get_time(node2)

            if time1 > time2:
                node1, node2 = node2, node1

            self.tracks_controller.delete_edges(edges=np.array([[node1, node2]]))

    def create_edge(self, event=None):
        """Calls the tracks controller to add an edge between the two currently selected nodes"""

        if len(self.selected_nodes) == 2:
            node1 = self.selected_nodes[0]
            node2 = self.selected_nodes[1]

            time1 = self.tracks.get_time(node1)
            time2 = self.tracks.get_time(node2)

            if time1 > time2:
                node1, node2 = node2, node1

            self.tracks_controller.add_edges(edges=np.array([[node1, node2]]))

    def undo(self, event=None):
        self.tracks_controller.undo()

    def redo(self, event=None):
        self.tracks_controller.redo()
