from __future__ import annotations

from typing import TYPE_CHECKING

import napari
import numpy as np
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr
from napari.utils import DirectLabelColormap

if TYPE_CHECKING:
    from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer


class TrackLabels(napari.layers.Labels):
    """Extended labels layer that holds the track information and emits
    and responds to dynamics visualization signals"""

    @property
    def _type_string(self) -> str:
        return "labels"  # to make sure that the layer is treated as labels layer for saving

    def __init__(
        self,
        viewer: napari.Viewer,
        data: np.array,
        name: str,
        opacity: float,
        scale: tuple,
        tracks_viewer: TracksViewer,
    ):
        self.tracks_viewer = tracks_viewer

        self.node_properties = {"node_id": [], "track_id": [], "t": [], "color": []}

        for node, node_data in self.tracks_viewer.tracks.graph.nodes(data=True):
            track_id = node_data[NodeAttr.TRACK_ID.value]
            self.node_properties["node_id"].append(node)
            self.node_properties["track_id"].append(track_id)
            self.node_properties["t"].append(node_data[NodeAttr.TIME.value])
            self.node_properties["color"].append(
                self.tracks_viewer.colormap.map(track_id)
            )

        colormap = DirectLabelColormap(
            color_dict={
                **dict(
                    zip(
                        self.node_properties["track_id"],
                        self.node_properties["color"],
                        strict=False,
                    )
                ),
                None: [0, 0, 0, 0],
            }
        )

        super().__init__(
            data=data,
            name=name,
            opacity=opacity,
            colormap=colormap,
            scale=scale,
        )

        self.viewer = viewer

        # Key bindings (should be specified both on the viewer (in tracks_viewer)
        # and on the layer to overwrite napari defaults)
        self.bind_key("q")(self.tracks_viewer.toggle_display_mode)
        self.bind_key("a")(self.tracks_viewer.create_edge)
        self.bind_key("d")(self.tracks_viewer.delete_node)
        self.bind_key("Delete")(self.tracks_viewer.delete_node)
        self.bind_key("b")(self.tracks_viewer.delete_edge)
        self.bind_key("s")(self.tracks_viewer.set_split_node)
        self.bind_key("e")(self.tracks_viewer.set_endpoint_node)
        self.bind_key("c")(self.tracks_viewer.set_linear_node)
        self.bind_key("z")(self.tracks_viewer.undo)
        self.bind_key("r")(self.tracks_viewer.redo)

        # Connect click events to node selection
        @self.mouse_drag_callbacks.append
        def click(_, event):
            if (
                event.type == "mouse_press"
                and self.mode == "pan_zoom"
                and not (
                    self.tracks_viewer.mode == "lineage"
                    and self.viewer.dims.ndisplay == 3
                )
            ):  # disable selecting in lineage mode in 3D
                label = self.get_value(
                    event.position,
                    view_direction=event.view_direction,
                    dims_displayed=event.dims_displayed,
                    world=True,
                )

                if (
                    label is not None
                    and label != 0
                    and self.colormap.map(label)[-1] != 0
                ):  # check opacity (=visibility) in the colormap
                    t_values = self.node_properties["t"]
                    track_ids = self.node_properties["track_id"]
                    index = np.where(
                        (t_values == event.position[0]) & (track_ids == label)
                    )[0]  # np.where returns a tuple with an array per dimension,
                    # here we apply it to a single dimension so take the first element
                    # (an array of indices fulfilling condition)
                    node_id = self.node_properties["node_id"][index[0]]
                    append = "Shift" in event.modifiers
                    self.tracks_viewer.selected_nodes.add(node_id, append)

        # Listen to paint events and changing the selected label
        self.events.paint.connect(self._on_paint)
        self.events.selected_label.connect(self._check_selected_label)

    def redo(self):
        """Overwrite the redo functionality of the labels layer and invoke redo action on the tracks_viewer.tracks_controller first"""

        self.tracks_viewer.redo()

    def undo(self):
        """Overwrite undo function and invoke undo action on the tracks_viewer.tracks_controller"""

        self.tracks_viewer.undo()

    def _on_paint(self, event):
        """Listen to the paint event and check which track_ids have changed"""

        current_timepoint = self.viewer.dims.current_step[
            0
        ]  # also pass on the current time point to know which node to select later

        self.tracks_viewer.tracks_controller.update_segmentations(
            event.value, current_timepoint
        )

    def _refresh(self):
        """Refresh the data in the labels layer"""

        self.data = self.tracks_viewer.tracks.segmentation[:, 0]
        self.node_properties = {"node_id": [], "track_id": [], "t": [], "color": []}

        for node, data in self.tracks_viewer.tracks.graph.nodes(data=True):
            track_id = data[NodeAttr.TRACK_ID.value]
            self.node_properties["node_id"].append(node)
            self.node_properties["track_id"].append(track_id)
            self.node_properties["t"].append(data[NodeAttr.TIME.value])
            self.node_properties["color"].append(
                self.tracks_viewer.colormap.map(track_id)
            )

        self.colormap = DirectLabelColormap(
            color_dict={
                **dict(
                    zip(
                        self.node_properties["track_id"],
                        self.node_properties["color"],
                        strict=False,
                    )
                ),
                None: [0, 0, 0, 0],
            }
        )

        self.refresh()

    def update_label_colormap(self, visible: list[int] | str) -> None:
        """Updates the opacity of the label colormap to highlight the selected label
        and optionally hide cells not belonging to the current lineage"""

        highlighted = [
            self.tracks_viewer.tracks.graph.nodes[node][NodeAttr.TRACK_ID.value]
            for node in self.tracks_viewer.selected_nodes
            if self.tracks_viewer.tracks.get_time(node)
            == self.viewer.dims.current_step[0]
        ]

        if len(highlighted) > 0:
            self.selected_label = highlighted[
                0
            ]  # set the first track_id to be the selected label color

        # update the opacity of the cyclic label colormap values according to whether nodes are visible/invisible/highlighted
        if visible == "all":
            self.colormap.color_dict = {
                key: np.array(
                    [*value[:-1], 0.6 if key is not None and key != 0 else value[-1]],
                    dtype=np.float32,
                )
                for key, value in self.colormap.color_dict.items()
            }

        else:
            self.colormap.color_dict = {
                key: np.array([*value[:-1], 0], dtype=np.float32)
                for key, value in self.colormap.color_dict.items()
            }
            for label in visible:
                # find the index in the cyclic label colormap
                self.colormap.color_dict[label][-1] = 0.6

        for label in highlighted:
            self.colormap.color_dict[label][-1] = 1  # full opacity

        self.colormap = DirectLabelColormap(
            color_dict=self.colormap.color_dict
        )  # create a new colormap from the updated colors (otherwise it does not refresh)

    def new_colormap(self):
        """Extended version of existing function, to emit refresh signal to also update colors in other layers/widgets"""

        super().new_colormap()
        self.tracks_viewer.colormap = self.colormap
        self.tracks_viewer._refresh()

    def _check_selected_label(self):
        """Check whether the selected label is larger than the current max_track_id and if so add it to the colormap (otherwise it draws in transparent color until the refresh event)"""

        if self.selected_label > self.tracks_viewer.tracks.max_track_id:
            self.events.selected_label.disconnect(
                self._check_selected_label
            )  # disconnect to prevent infinite loop, since setting the colormap emits a selected_label event
            self.colormap.color_dict[self.selected_label] = (
                self.tracks_viewer.colormap.map(self.selected_label)
            )
            self.colormap = DirectLabelColormap(color_dict=self.colormap.color_dict)
            self.events.selected_label.connect(
                self._check_selected_label
            )  # connect again
