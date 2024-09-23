from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import napari
import numpy as np
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr
from napari.utils import CyclicLabelColormap, DirectLabelColormap

if TYPE_CHECKING:
    from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer


def create_selection_label_cmap(
    color_dict_rgb: dict, visible: list[int] | str, highlighted: list[int]
) -> DirectLabelColormap:
    """Generates a label colormap with three possible opacity values
    (0 for invisibible labels, 0.6 for visible labels, and 1 for selected labels)"""

    color_dict_rgb_temp = copy.deepcopy(color_dict_rgb)
    if visible == "all":
        for key in color_dict_rgb_temp:
            if key is not None:
                color_dict_rgb_temp[key][-1] = 0.6  # set opacity to 0.6
    else:
        for label in visible:
            if label in color_dict_rgb_temp:
                color_dict_rgb_temp[label][-1] = 0.6  # set opacity to 0.6

    for label in highlighted:
        if label != 0 and label in color_dict_rgb_temp:
            color_dict_rgb_temp[label][-1] = 1  # set opacity to full

    return DirectLabelColormap(color_dict=color_dict_rgb_temp)


class TrackLabels(napari.layers.Labels):
    """Extended labels layer that holds the track information and emits
    and responds to dynamics visualization signals"""

    def __init__(
        self,
        viewer: napari.Viewer,
        data: np.array,
        name: str,
        colormap: CyclicLabelColormap,
        opacity: float,
        scale: tuple,
        tracks_viewer: TracksViewer,
    ):
        self.nodes = list(tracks_viewer.tracks.graph.nodes)
        props = {
            "node_id": self.nodes,
            "track_id": [
                data[NodeAttr.TRACK_ID.value]
                for _, data in tracks_viewer.tracks.graph.nodes(data=True)
            ],
            "t": [tracks_viewer.tracks.get_time(node) for node in self.nodes],
        }
        super().__init__(
            data=data,
            name=name,
            opacity=opacity,
            colormap=colormap,
            properties=props,
            scale=scale,
        )

        self.viewer = viewer
        self.tracks_viewer = tracks_viewer

        self.base_label_color_dict = self.create_label_color_dict(
            np.unique(self.properties["track_id"]), colormap=colormap
        )

        @self.mouse_drag_callbacks.append
        def click(_, event):
            if event.type == "mouse_press" and self.mode == "pan_zoom":
                label = self.get_value(
                    event.position,
                    view_direction=event.view_direction,
                    dims_displayed=event.dims_displayed,
                    world=True,
                )

                if label is not None and label != 0:
                    t_values = self.properties["t"]
                    track_ids = self.properties["track_id"]
                    index = np.where(
                        (t_values == event.position[0]) & (track_ids == label)
                    )[0]  # np.where returns a tuple with an array per dimension,
                    # here we apply it to a single dimension so take the first element
                    # (an array of indices fulfilling condition)
                    node_id = self.nodes[index[0]]
                    append = "Shift" in event.modifiers
                    self.tracks_viewer.selected_nodes.add(node_id, append)

        self.events.paint.connect(self._on_paint)

    def _on_paint(self, event):
        """Listen to the paint event and check which track_ids have changed"""

        old_values = list(np.unique(np.concatenate([ev[1] for ev in event.value])))
        new_value = [event.value[-1][-1]]

        # check which time points are affected (user might paint in 3 dimensions on 2D + time data)
        time_points = list(
            np.unique(np.concatenate([ev[0][0] for ev in event.value]))
        )  # have to check the first array axis of the first element (the array) of all elements in event.value (just the last one is not always sufficient)

        changed_track_ids = old_values + new_value
        changed_track_ids = [value for value in changed_track_ids if value != 0]

        current_timepoint = self.viewer.dims.current_step[
            0
        ]  # also pass on the current time point to know which node to select later

        self.tracks_viewer.tracks_controller.update_segmentations(
            time_points, current_timepoint, changed_track_ids
        )

    def _refresh(self):
        """Refresh the data in the labels layer"""

        self.data = np.squeeze(self.tracks_viewer.tracks.segmentation)
        self.nodes = list(self.tracks_viewer.tracks.graph.nodes)

        self.properties = {
            "node_id": self.nodes,
            "track_id": [
                data[NodeAttr.TRACK_ID.value]
                for _, data in self.tracks_viewer.tracks.graph.nodes(data=True)
            ],
            "t": [self.tracks_viewer.tracks.get_time(node) for node in self.nodes],
        }

        colormap = napari.utils.colormaps.label_colormap(
            49,
            seed=0.5,
            background_value=0,
        )

        self.base_label_color_dict = self.create_label_color_dict(
            np.unique(self.properties["track_id"]), colormap=colormap
        )

        self.refresh()

    def create_label_color_dict(
        self, labels: list[int], colormap: CyclicLabelColormap
    ) -> dict:
        """Extract the label colors to generate a base colormap, but keep opacity at 0"""

        color_dict_rgb = {None: [0.0, 0.0, 0.0, 0.0]}

        # Iterate over unique labels
        for label in labels:
            color = colormap.map(label)
            color[-1] = (
                0  # Set opacity to 0 (will be replaced when a label is visible/invisible/selected)
            )
            color_dict_rgb[label] = color

        return color_dict_rgb

    def update_label_colormap(self, visible: list[int] | str) -> None:
        """Updates the opacity of the label colormap to highlight the selected label
        and optionally hide cells not belonging to the current lineage"""

        highlighted = [
            self.tracks_viewer.tracks.graph.nodes[node][NodeAttr.TRACK_ID.value]
            for node in self.tracks_viewer.selected_nodes
            if self.tracks_viewer.tracks.get_time(node)
            == self.viewer.dims.current_step[0]
        ]

        if self.base_label_color_dict is not None:
            colormap = create_selection_label_cmap(
                self.base_label_color_dict,
                visible=visible,
                highlighted=highlighted,
            )
            self.colormap = colormap
