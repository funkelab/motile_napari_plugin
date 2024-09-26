from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional

import napari
import numpy as np
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr
from psygnal import Signal

from motile_plugin.data_model import NodeType, Tracks
from motile_plugin.data_model.tracks_controller import TracksController
from motile_plugin.data_views.views.layers.track_graph import TrackGraph
from motile_plugin.data_views.views.layers.track_labels import TrackLabels
from motile_plugin.data_views.views.layers.track_points import TrackPoints
from motile_plugin.data_views.views.tree_view.tree_widget_utils import (
    extract_lineage_tree,
)

from .node_selection_list import NodeSelectionList
from .tracks_list import TracksList


@dataclass
class TracksLayerGroup:
    tracks_layer: TrackGraph | None = None
    seg_layer: TrackLabels | None = None
    points_layer: TrackPoints | None = None


class TracksViewer:
    """Purposes of the TracksViewer:
    - Emit signals that all widgets should use to update selection or update
        the currently displayed Tracks object
    - Storing the currently displayed tracks
    - Store shared rendering information like colormaps (or symbol maps)
    - Interacting with the napari.Viewer by adding and removing layers
    """

    tracks_updated: ClassVar[Signal[Optional[bool]]] = Signal()
    undo_seg = Signal()
    redo_seg = Signal()

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
        # TODO: separate and document keybinds
        self.viewer.bind_key("q")(self.toggle_display_mode)
        self.viewer.bind_key("a")(self.create_edge)
        self.viewer.bind_key("d")(self.delete_node)
        self.viewer.bind_key("Delete")(self.delete_node)
        self.viewer.bind_key("b")(self.delete_edge)
        self.viewer.bind_key("s")(self.set_split_node)
        self.viewer.bind_key("e")(self.set_endpoint_node)
        self.viewer.bind_key("c")(self.set_linear_node)
        self.viewer.bind_key("z")(self.undo)
        self.viewer.bind_key("r")(self.redo)

        self.selected_nodes = NodeSelectionList()
        self.selected_nodes.list_updated.connect(self.update_selection)

        self.tracking_layers = TracksLayerGroup()
        self.tracks = None

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
        self.tracks_list = TracksList()
        self.tracks_list.view_tracks.connect(self.update_tracks)

    def remove_napari_layer(self, layer: napari.layers.Layer | None) -> None:
        """Remove a layer from the napari viewer, if present"""
        if layer and layer in self.viewer.layers:
            self.viewer.layers.remove(layer)

    def remove_napari_layers(self) -> None:
        """Remove all tracking layers from the viewer"""
        self.remove_napari_layer(self.tracking_layers.tracks_layer)
        self.remove_napari_layer(self.tracking_layers.seg_layer)
        self.remove_napari_layer(self.tracking_layers.points_layer)

    def add_napari_layers(self) -> None:
        """Add new tracking layers to the viewer"""
        if self.tracking_layers.tracks_layer is not None:
            self.viewer.add_layer(self.tracking_layers.tracks_layer)
        if self.tracking_layers.seg_layer is not None:
            self.viewer.add_layer(self.tracking_layers.seg_layer)
        if self.tracking_layers.points_layer is not None:
            self.viewer.add_layer(self.tracking_layers.points_layer)

    def _refresh(self, node: str | None = None) -> None:
        """Call refresh function on napari layers and the submit signal that tracks are updated
        Restore the selected_nodes, if possible
        """

        if len(self.selected_nodes) > 0 and any(
            not self.tracks.graph.has_node(node) for node in self.selected_nodes
        ):
            self.selected_nodes.reset()

        if self.tracking_layers.points_layer is not None:
            self.tracking_layers.points_layer._refresh()
        if self.tracking_layers.tracks_layer is not None:
            self.tracking_layers.tracks_layer._refresh()
        if self.tracking_layers.seg_layer is not None:
            self.tracking_layers.seg_layer._refresh()

        # if a new node was added, we would like to select this one now
        if node is not None:
            self.selected_nodes.add(node)

        elif len(self.selected_nodes) > 0:
            self.selected_nodes.list_updated.emit()  # to restore selection in all components

        self.tracks_updated.emit()

    def update_tracks(self, tracks: Tracks, name: str) -> None:
        """Stop viewing a previous set of tracks and replace it with a new one.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            tracks (motile_plugin.core.Tracks): The tracks to visualize in napari.
            name (str): The name of the tracks to display in the layer names
        """
        self.selected_nodes._list = []
        self.tracks = tracks
        self.tracks_controller = TracksController(self.tracks)

        # listen to refresh signals from the tracks
        if self.tracks is not None:
            self.tracks.refresh.connect(
                self._refresh
            )  # TODO what if the connection exists already?

        # Remove old layers if necessary
        self.remove_napari_layers()

        # deactivate the input labels layer
        for layer in self.viewer.layers:
            if isinstance(layer, napari.layers.Labels):
                layer.visible = False

        # Create new layers
        if tracks is not None and tracks.segmentation is not None:
            self.tracking_layers.seg_layer = TrackLabels(
                viewer=self.viewer,
                data=tracks.segmentation[:, 0],
                name=name + "_seg",
                opacity=0.9,
                scale=self.tracks.scale,
                tracks_viewer=self,
            )

        else:
            self.tracking_layers.seg_layer = None

        if (
            tracks is None
            or tracks.graph is None
            or tracks.graph.number_of_nodes() == 0
        ):
            self.tracking_layers.tracks_layer = None
            self.tracking_layers.points_layer = None
        else:
            self.tracking_layers.tracks_layer = TrackGraph(
                viewer=self.viewer,
                name=name + "_tracks",
                tracks_viewer=self,
            )

            self.tracking_layers.points_layer = TrackPoints(
                viewer=self.viewer,
                name=name + "_points",
                symbolmap=self.symbolmap,
                tracks_viewer=self,
            )

        self.add_napari_layers()
        self.set_display_mode("all")
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
        if self.tracking_layers.seg_layer is not None:
            self.tracking_layers.seg_layer.update_label_colormap(visible)
        if self.tracking_layers.points_layer is not None:
            self.tracking_layers.points_layer.update_point_outline(visible)
        if self.tracking_layers.tracks_layer is not None:
            self.tracking_layers.tracks_layer.update_track_visibility(visible)

    def filter_visible_nodes(self) -> list[int]:
        """Construct a list of track_ids that should be displayed"""
        if self.mode == "lineage":
            visible = []
            for node in self.selected_nodes:
                visible += extract_lineage_tree(self.tracks.graph, node)
            if self.tracks is None or self.tracks.graph is None:
                return []
            return list(
                {
                    self.tracks.graph.nodes[node][NodeAttr.TRACK_ID.value]
                    for node in visible
                }
            )
        else:
            return "all"

    def update_selection(self) -> None:
        """Sets the view and triggers visualization updates in other components"""

        self.set_napari_view()
        visible = self.filter_visible_nodes()
        if self.tracking_layers.seg_layer is not None:
            self.tracking_layers.seg_layer.update_label_colormap(visible)
        self.tracking_layers.points_layer.update_point_outline(visible)
        self.tracking_layers.tracks_layer.update_track_visibility(visible)

    def set_napari_view(self) -> None:
        """Adjust the current_step of the viewer to jump to the last item of the selected_nodes list"""
        if len(self.selected_nodes) > 0:
            node = self.selected_nodes[-1]
            location = self.tracks.get_location(node, incl_time=True)
            assert (
                len(location) == self.viewer.dims.ndim
            ), f"Location {location} does not match viewer number of dims {self.viewer.dims.ndim}"

            step = list(self.viewer.dims.current_step)
            for dim in self.viewer.dims.not_displayed:
                step[dim] = int(
                    location[dim] + 0.5
                )  # use the scaled location, since the 'step' in viewer.dims.range already accounts for the scaling

            self.viewer.dims.current_step = step

            # check whether the new coordinates are inside or outside the field of view, then adjust the camera if needed
            example_layer = self.tracking_layers.points_layer  # the points layer is not scaled by the 'scale' attribute, because it directly reads the scaled coordinates. Therefore, no rescaling is necessary to compute the camera center
            corner_coordinates = example_layer.corner_pixels

            # check which dimensions are shown, the first dimension is displayed on the x axis, and the second on the y_axis
            dims_displayed = self.viewer.dims.displayed
            x_dim = dims_displayed[-1]
            y_dim = dims_displayed[-2]

            # find corner pixels for the displayed axes
            _min_x = corner_coordinates[0][x_dim]
            _max_x = corner_coordinates[1][x_dim]
            _min_y = corner_coordinates[0][y_dim]
            _max_y = corner_coordinates[1][y_dim]

            # check whether the node location falls within the corner spatial range
            if not (
                (location[x_dim] > _min_x and location[x_dim] < _max_x)
                and (location[y_dim] > _min_y and location[y_dim] < _max_y)
            ):
                camera_center = self.viewer.camera.center

                # set the center y and x to the center of the node, by using the index of the currently displayed dimensions
                self.viewer.camera.center = (
                    camera_center[0],
                    location[
                        y_dim
                    ],  # camera center is calculated in scaled coordinates, and the optional labels layer is scaled by the layer.scale attribute
                    location[x_dim],
                )

    def delete_node(self, event=None):
        """Calls the tracks controller to delete currently selected nodes"""

        self.tracks_controller.delete_nodes(np.array(self.selected_nodes._list))

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

            self.tracks_controller.add_edges(
                edges=np.array([[node1, node2]]), attributes={}
            )

    def undo(self, event=None):
        action_to_undo = self.tracks_controller.actions[
            self.tracks_controller.last_action
        ]
        if action_to_undo.update_seg:
            self.undo_seg.emit()
        self.tracks_controller.last_action -= 1
        inverse_action = action_to_undo.inverse()
        inverse_action.apply()
        self.tracks.refresh()

    def redo(self, event=None):
        if self.tracks_controller.last_action < len(self.tracks_controller.actions) - 1:
            action_to_redo = self.tracks_controller.actions[
                self.tracks_controller.last_action + 1
            ]
            if action_to_redo.update_seg:
                self.redo_seg.emit()
            self.tracks_controller.last_action += 1
            action_to_redo.apply()
            self.tracks.refresh()
