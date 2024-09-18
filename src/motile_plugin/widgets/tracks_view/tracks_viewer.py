from dataclasses import dataclass

import napari
import numpy as np
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids
from psygnal import Signal

from motile_plugin.core import NodeType, Tracks
from motile_plugin.layers.track_graph import TrackGraph
from motile_plugin.layers.track_labels import TrackLabels
from motile_plugin.layers.track_points import TrackPoints
from motile_plugin.utils.node_selection import NodeSelectionList
from motile_plugin.utils.relabel_segmentation import relabel_segmentation
from motile_plugin.utils.tree_widget_utils import (
    extract_lineage_tree,
)


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

    tracks_updated = Signal()

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
        self.viewer.bind_key("t")(self.toggle_display_mode)

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

    def view_external_tracks(self, tracks: Tracks, name: str) -> None:
        """View tracks created externally. Assigns tracklet ids, adds a hypothesis
        dimension to the segmentation, and relabels the segmentation based on the
        assigned track ids. Then calls update_tracks.

        Args:
            tracks (Tracks): A tracks object to view, created externally from the plugin
            name (str): The name to display in napari layers
        """
        tracks.graph, _ = assign_tracklet_ids(tracks.graph)
        tracks.segmentation = np.expand_dims(tracks.segmentation, axis=1)
        tracks.segmentation = relabel_segmentation(tracks.graph, tracks.segmentation)
        self.update_tracks(tracks, name)

    def update_tracks(self, tracks: Tracks, name: str) -> None:
        """Stop viewing a previous set of tracks and replace it with a new one.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            tracks (motile_plugin.core.Tracks): The tracks to visualize in napari.
            name (str): The name of the tracks to display in the layer names
        """
        self.selected_nodes._list = []
        self.tracks = tracks
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
                colormap=self.colormap,
                tracks=self.tracks,
                opacity=0.9,
                selected_nodes=self.selected_nodes,
                scale=self.tracks.scale,
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
                tracks=tracks,
                name=name + "_tracks",
                colormap=self.colormap,
            )
            self.tracking_layers.points_layer = TrackPoints(
                viewer=self.viewer,
                tracks=tracks,
                name=name + "_points",
                selected_nodes=self.selected_nodes,
                symbolmap=self.symbolmap,
                colormap=self.colormap,
            )

        self.tracks_updated.emit()
        self.add_napari_layers()
        self.set_display_mode("all")

    def toggle_display_mode(self, event=None) -> None:
        """Toggle the display mode between available options"""

        if self.mode == "lineage":
            self.set_display_mode("all")
        else:
            self.set_display_mode("lineage")

    def set_display_mode(self, mode: str) -> None:
        """Update the display mode and call to update colormaps for points, labels,
        and tracks

        Args:
            mode (str): "all" or "lineage"
        """

        # toggle between 'all' and 'lineage'
        if mode == "lineage":
            self.mode = "lineage"
            self.viewer.text_overlay.text = "Toggle Display [T]\n Lineage"
        else:
            self.mode = "all"
            self.viewer.text_overlay.text = "Toggle Display [T]\n All"

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
                {self.tracks.graph.nodes[node]["tracklet_id"] for node in visible}
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
        """Adjust the current_step of the viewer to jump to the last item of the
        selected_nodes list"""
        if len(self.selected_nodes) > 0:
            node = self.selected_nodes[-1]
            location = self.tracks.get_location(node, incl_time=True)
            assert len(location) == self.viewer.dims.ndim, (
                f"Location {location} does not match viewer number of dims"
                f"{self.viewer.dims.ndim}"
            )

            step = list(self.viewer.dims.current_step)
            for dim in self.viewer.dims.not_displayed:
                # use the scaled location, since the 'step' in viewer.dims.range already
                # accounts for the scaling
                step[dim] = int(location[dim] + 0.5)

            self.viewer.dims.current_step = step

            # Check whether the new coordinates are inside or outside the field of view,
            # then adjust the camera if needed.
            # The points layer is not scaled by the 'scale' attribute, because it
            # directly reads the scaled coordinates. Therefore, no rescaling is
            # necessary to compute the camera center
            example_layer = self.tracking_layers.points_layer
            corner_coordinates = example_layer.corner_pixels

            # check which dimensions are shown, the first dimension is displayed on the
            # x axis, and the second on the y_axis
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

                # set the center y and x to the center of the node, by using the index
                # of the currently displayed dimensions
                self.viewer.camera.center = (
                    camera_center[0],
                    location[
                        y_dim
                    ],  # camera center is calculated in scaled coordinates, and the
                    # optional labels layer is scaled by the layer.scale attribute
                    location[x_dim],
                )
