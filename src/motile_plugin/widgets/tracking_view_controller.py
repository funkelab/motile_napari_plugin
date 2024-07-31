import copy
from dataclasses import dataclass
from typing import Dict

import napari
import numpy as np
from motile_toolbox.visualization import to_napari_tracks_layer
from napari.layers import Labels, Tracks
from psygnal import Signal

from motile_plugin.backend.motile_run import MotileRun

from ..utils.colormaps import (
    create_label_color_dict,
    create_selection_label_cmap,
    create_track_layer_colormap,
)
from ..utils.points_utils import construct_points_layer
from ..utils.tree_widget_utils import extract_lineage_tree


@dataclass
class TrackingLayerGroup:
    tracks_layer: napari.layers.Tracks | None = None
    seg_layer: napari.layers.Labels | None = None
    points_layer: napari.layers.Points | None = None


class TrackingViewController:
    selection_updated = Signal(object)
    tracking_layers_updated = Signal(object)

    @classmethod
    def get_instance(cls, viewer=None):
        if not hasattr(cls, "_instance"):
            print("Making new tracking view controller")
            if viewer is None:
                raise ValueError("Make a viewer first please!")
            cls._instance = TrackingViewController(viewer)
        return cls._instance

    def __init__(self, viewer: napari.viewer):
        self.viewer = viewer
        self.viewer.bind_key("t")(self.toggle_display_mode)
        self.selected_nodes = []
        self.tracking_layers: TrackingLayerGroup = TrackingLayerGroup()
        self.colormap = napari.utils.colormaps.label_colormap(
            49,
            seed=0.5,
            background_value=0,
        )
        self.run = None
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

    def update_napari_layers(self, run: MotileRun) -> None:
        """Remove the old napari layers and update them according to the run output.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            run (MotileRun): The run outputs to visualize in napari.
        """

        self.run = run  # keep the run information accessible

        # Remove old layers if necessary
        self.remove_napari_layers()
        for layer in self.viewer.layers:
            layer.visible = False  # deactivate the input layer

        # create colormap dictionary for updating label colors
        if run.track_df is not None:
            self.base_label_color_dict = create_label_color_dict(
                run.track_df["track_id"].unique(), colormap=self.colormap
            )

        # Create new layers
        if run.output_segmentation is not None:

            self.tracking_layers.seg_layer = Labels(
                run.output_segmentation[:, 0],
                name=run.run_name + "_seg",
                colormap=self.colormap,
                properties=run.track_df,
                opacity=0.9,
            )

            # add callback for selecting nodes on the labels layer
            @self.tracking_layers.seg_layer.mouse_drag_callbacks.append
            def click(layer, event):
                if event.type == "mouse_press":
                    position = event.position
                    value = layer.get_value(
                        position,
                        view_direction=event.view_direction,
                        dims_displayed=event.dims_displayed,
                        world=True,
                    )
                    if value is not None and value != 0:

                        index = np.where(
                            (layer.properties["t"] == position[0])
                            & (layer.properties["track_id"] == value)
                        )[0]
                        node = {
                            key: value[index][0]
                            for key, value in layer.properties.items()
                        }
                        if len(node) > 0:
                            append = "Shift" in event.modifiers
                            self.select_node(node, add_to_existing=append)

        else:
            self.tracking_layers.seg_layer = None

        if run.tracks is None or run.tracks.number_of_nodes() == 0:
            self.tracking_layers.tracks_layer = None
            self.tracking_layers.points_layer = None
        else:
            # add tracks layer
            track_data, track_props, track_edges = to_napari_tracks_layer(
                run.tracks
            )

            self.tracking_layers.tracks_layer = Tracks(
                track_data,
                properties=track_props,
                graph=track_edges,
                name=run.run_name + "_tracks",
                tail_length=3,
            )
            self.tracks_layer_graph = copy.deepcopy(
                self.tracking_layers.tracks_layer.graph
            )  # for restoring graph later

            # deal with the colormap issue for the trackslayer, also apply to points layer
            colormap_name = "track_colors"
            create_track_layer_colormap(
                tracks=self.tracking_layers.tracks_layer,
                base_colormap=self.colormap,
                name=colormap_name,
            )
            self.tracking_layers.tracks_layer.colormap = colormap_name

            # construct points layer and add click callback
            self.tracking_layers.points_layer = construct_points_layer(
                data=run.track_df, name=run.run_name + "_points"
            )

            @self.tracking_layers.points_layer.mouse_drag_callbacks.append
            def click(layer, event):
                if event.type == "mouse_press":
                    point_index = layer.get_value(
                        event.position,
                        view_direction=event.view_direction,
                        dims_displayed=event.dims_displayed,
                        world=True,
                    )
                    if point_index is not None:
                        node_id = layer.properties["node_id"][point_index]
                        index = [
                            i
                            for i, nid in enumerate(
                                layer.properties["node_id"]
                            )
                            if nid == node_id
                        ][0]
                        node = {
                            key: value[index]
                            for key, value in layer.properties.items()
                        }

                        if len(node) > 0:
                            append = "Shift" in event.modifiers
                            self.select_node(node, add_to_existing=append)

        self.tracking_layers_updated.emit(run)
        self.add_napari_layers()
        self.set_display_mode("all")

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
            self.viewer.text_overlay.text = "Toggle Display [T]\n Lineage"
        else:
            self.mode = "all"
            self.viewer.text_overlay.text = "Toggle Display [T]\n All Cells"

        self.viewer.text_overlay.visible = True
        visible = self.filter_visible_nodes()
        self.update_label_colormap(visible)
        self.update_point_outline(visible)
        self.update_track_visibility(visible)

    def filter_visible_nodes(self) -> list[int]:
        """Construct a list of track_ids that should be displayed"""
        if self.mode == "lineage":
            if len(self.selected_nodes) == 0:
                return []
            else:
                visible = extract_lineage_tree(
                    self.run.tracks, self.selected_nodes[0]["node_id"]
                )
                return list(
                    np.unique(
                        self.run.track_df.loc[
                            self.run.track_df["node_id"].isin(visible),
                            "track_id",
                        ].values
                    )
                )
        else:
            return "all"

    def select_node(self, node: Dict, add_to_existing=False) -> None:
        """Updates the list of selected nodes and triggers visualization updates in other components"""

        if add_to_existing and len(self.selected_nodes) == 1:
            self.selected_nodes.append(node)
        else:
            self.selected_nodes = [node]
        self.selection_updated.emit(self.selected_nodes)
        self.set_napari_view()

        visible = self.filter_visible_nodes()

        self.update_point_outline(visible)
        self.update_label_colormap(visible)
        self.update_track_visibility(visible)

    def update_label_colormap(self, visible: list[int] | str) -> None:
        """Updates the opacity of the label colormap to highlight the selected label and optionally hide cells not belonging to the current lineage"""

        highlighted = [
            node["track_id"]
            for node in self.selected_nodes
            if node["t"] == self.viewer.dims.current_step[0]
        ]
        if self.base_label_color_dict is not None:
            colormap = create_selection_label_cmap(
                self.base_label_color_dict,
                visible=visible,
                highlighted=highlighted,
            )
            self.tracking_layers.seg_layer.colormap = colormap

    def update_point_outline(self, visible: list[int] | str) -> None:
        """Update the outline color of the selected points and visibility according to display mode"""

        if visible == "all":
            self.tracking_layers.points_layer.shown[:] = True
        else:
            indices = self.run.track_df[
                self.run.track_df["track_id"].isin(visible)
            ].index.tolist()

            self.tracking_layers.points_layer.shown[:] = False
            self.tracking_layers.points_layer.shown[indices] = True

        self.tracking_layers.points_layer.border_color = [1, 1, 1, 1]
        for node in self.selected_nodes:
            self.tracking_layers.points_layer.border_color[node["index"]] = (
                0,
                1,
                1,
                1,
            )
        self.tracking_layers.points_layer.refresh()

    def update_track_visibility(self, visible: list[int] | str) -> None:
        """Optionally show only the tracks of a current lineage"""

        if visible == "all":
            self.tracking_layers.tracks_layer.track_colors[:, 3] = 1
            self.tracking_layers.tracks_layer.graph = self.tracks_layer_graph
        else:
            track_id_mask = np.isin(
                self.tracking_layers.tracks_layer.properties["track_id"],
                visible,
            )
            self.tracking_layers.tracks_layer.graph = {
                key: self.tracks_layer_graph[key]
                for key in visible
                if key in self.tracks_layer_graph
            }

            self.tracking_layers.tracks_layer.track_colors[:, 3] = 0
            self.tracking_layers.tracks_layer.track_colors[
                track_id_mask, 3
            ] = 1
            if len(self.tracking_layers.tracks_layer.graph.items()) == 0:
                self.tracking_layers.tracks_layer.display_graph = False  # empty dicts to not trigger update (bug?) so disable the graph entirely as a workaround
            else:
                self.tracking_layers.tracks_layer.display_graph = True

    def set_napari_view(self) -> None:
        """Adjust the current_step of the viewer to jump to the last item of the selected_nodes list"""

        if len(self.selected_nodes) > 0:
            node = self.selected_nodes[-1]

            # Check for 'z' key and update step if exists
            step = list(self.viewer.dims.current_step)
            step[0] = node["t"]
            if "z" in node:
                z = node["z"]
                step[1] = int(z)
            self.viewer.dims.current_step = step

            # check whether the new coordinates are inside or outside the field of view, then adjust the camera if needed
            if self.viewer.dims.ndisplay == 2:  # no 3D solution yet
                camera_pos = self.viewer.window._qt_window._qt_viewer.canvas.view.camera.get_state()[
                    "rect"
                ]._pos  # top left corner
                camera_size = self.viewer.window._qt_window._qt_viewer.canvas.view.camera.get_state()[
                    "rect"
                ].size

                if not (
                    (
                        node["x"] > camera_pos[0]
                        and node["x"] < camera_pos[0] + camera_size[0]
                    )
                    and (
                        node["y"] > camera_pos[1]
                        and node["y"] < camera_pos[1] + camera_size[1]
                    )
                ):
                    camera_center = self.viewer.camera.center

                    self.viewer.camera.center = (
                        camera_center[0],
                        node["y"],
                        node["x"],
                    )
