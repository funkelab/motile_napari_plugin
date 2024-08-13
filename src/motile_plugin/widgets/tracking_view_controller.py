from dataclasses import dataclass

import napari
import numpy as np
from motile_toolbox.candidate_graph import NodeAttr
from psygnal import Signal

from motile_plugin.backend.motile_run import MotileRun
from motile_plugin.core import NodeType

from ..layers.tracked_graph import TrackGraph
from ..layers.tracked_labels import TrackLabels
from ..layers.tracked_points import TrackPoints
from ..utils.node_selection import NodeSelectionList
from ..utils.tree_widget_utils import (
    extract_lineage_tree,
    extract_sorted_tracks,
)


@dataclass
class TrackingLayerGroup:
    tracks_layer: TrackGraph | None = None
    seg_layer: TrackLabels | None = None
    points_layer: TrackPoints | None = None


class TrackingViewController:
    """Purposes of the TrackingViewController:
    - Emit signals that all widgets should use to update selection or update
        the currently displayed run
    - Storing the currently displayed run and a dataframe with rendering information
        for that run
    - Store shared rendering information like colormaps (or symbol maps)
    - Interacting with the napari.Viewer by adding and removing layers
    """

    tracking_layers_updated = Signal()  # rename to run_updated?

    @classmethod
    def get_instance(cls, viewer=None):
        if not hasattr(cls, "_instance"):
            print("Making new tracking view controller")
            if viewer is None:
                raise ValueError("Make a viewer first please!")
            cls._instance = TrackingViewController(viewer)
        return cls._instance

    def __init__(
        self,
        viewer: napari.viewer,
        time_attr: str = NodeAttr.TIME.value,
        pos_attr: str = NodeAttr.POS.value,
    ):
        self.viewer = viewer
        self.viewer.bind_key("t")(self.toggle_display_mode)
        self.selected_nodes = NodeSelectionList()
        self.selected_nodes.list_updated.connect(self.select_node)
        self.tracking_layers: TrackingLayerGroup = TrackingLayerGroup()
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
        # TODO: remove unnecessary items
        self.run = None
        self.time_attr = time_attr
        self.pos_attr = pos_attr
        self.track_df = None
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

    def update_napari_layers(
        self, run: MotileRun, time_attr=None, pos_attr=None
    ) -> None:
        """Remove the old napari layers and update them according to the run output.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            run (MotileRun): The run outputs to visualize in napari.
        """
        self.selected_nodes._list = []
        self.run = run  # keep the run information accessible
        if time_attr is not None:
            self.time_attr = time_attr
        if pos_attr is not None:
            self.pos_attr = pos_attr

        graph = None if self.tracks is None else run.tracks.graph
        self.track_df = extract_sorted_tracks(
            graph,
            self.colormap,
            time_attr=self.time_attr,
            pos_attr=self.pos_attr,
        )

        # Remove old layers if necessary
        self.remove_napari_layers()
        for layer in self.viewer.layers:
            if isinstance(layer, napari.layers.Labels):
                layer.visible = False  # deactivate the input labels layer

        # Create new layers
        if run.tracks is not None and run.tracks.segmentation is not None:
            self.tracking_layers.seg_layer = TrackLabels(
                viewer=self.viewer,
                data=run.tracks.segmentation[:, 0],
                name=run.run_name + "_seg",
                colormap=self.colormap,
                track_df=self.track_df,
                opacity=0.9,
                selected_nodes=self.selected_nodes,
            )

        else:
            self.tracking_layers.seg_layer = None

        if (
            run.tracks is None
            or run.tracks.graph is None
            or run.tracks.graph.number_of_nodes() == 0
        ):
            self.tracking_layers.tracks_layer = None
            self.tracking_layers.points_layer = None
        else:
            self.tracking_layers.tracks_layer = TrackGraph(
                viewer=self.viewer,
                data=run.tracks.graph,
                name=run.run_name + "_tracks",
                colormap=self.colormap,
                time_attr=self.time_attr,
                pos_attr=self.pos_attr,
            )
            self.tracking_layers.points_layer = TrackPoints(
                viewer=self.viewer,
                tracks=run.tracks,
                name=run.run_name + "_points",
                selected_nodes=self.selected_nodes,
                symbolmap=self.symbolmap,
                colormap=self.colormap,
            )

        self.tracking_layers_updated.emit()
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
            if len(self.selected_nodes) == 0:
                return []
            else:
                visible = extract_lineage_tree(
                    self.run.tracks, self.selected_nodes[0]["node_id"]
                )
                return list(
                    np.unique(
                        self.track_df.loc[
                            self.track_df["node_id"].isin(visible),
                            "track_id",
                        ].values
                    )
                )
        else:
            return "all"

    def select_node(self) -> None:
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
