import copy
from typing import Dict, List

import napari
import numpy as np
import pandas as pd
from napari.utils import CyclicLabelColormap, DirectLabelColormap

from motile_plugin.core import Tracks

from ..utils.node_selection import NodeSelectionList


def create_selection_label_cmap(
    color_dict_rgb: Dict, visible: List[int] | str, highlighted: List[int]
) -> DirectLabelColormap:
    """Generates a label colormap with three possible opacity values (0 for invisibible labels, 0.6 for visible labels, and 1 for selected labels)"""

    color_dict_rgb_temp = copy.deepcopy(color_dict_rgb)
    if visible == "all":
        for key in color_dict_rgb_temp:
            if key is not None:
                color_dict_rgb_temp[key][-1] = 0.6  # set opacity to 0.6
    else:
        for label in visible:
            color_dict_rgb_temp[label][-1] = 0.6  # set opacity to 0.6

    for label in highlighted:
        if label != 0:
            color_dict_rgb_temp[label][-1] = 1  # set opacity to full

    return DirectLabelColormap(color_dict=color_dict_rgb_temp)


class TrackLabels(napari.layers.Labels):
    """Extended labels layer that holds the track information and emits and responds to dynamics visualization signals"""

    def __init__(
        self,
        viewer: napari.Viewer,
        data: np.array,
        name: str,
        colormap: CyclicLabelColormap,
        track_df: pd.DataFrame,  # TODO: update to not use df like points layer
        tracks: Tracks,
        opacity: float,
        selected_nodes: NodeSelectionList,
    ):
        super().__init__(
            data=data,
            name=name,
            opacity=opacity,
            colormap=colormap,
            properties=track_df,
        )

        self.viewer = viewer
        self.selected_nodes = selected_nodes
        self.tracks = tracks

        self.base_label_color_dict = self.create_label_color_dict(
            track_df["track_id"].unique(), colormap=colormap
        )

        @self.mouse_drag_callbacks.append
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
                        self.selected_nodes.add(node, append)

    def create_label_color_dict(
        self, labels: List[int], colormap: CyclicLabelColormap
    ) -> Dict:
        """Extract the label colors to generate a base colormap, but keep opacity at 0"""

        color_dict_rgb = {None: [0.0, 0.0, 0.0, 0.0]}

        # Iterate over unique labels
        for label in labels:
            color = colormap.map(label)
            color[
                -1
            ] = 0  # Set opacity to 0 (will be replaced when a label is visible/invisible/selected)
            color_dict_rgb[label] = color

        return color_dict_rgb

    def update_label_colormap(self, visible: list[int] | str) -> None:
        """Updates the opacity of the label colormap to highlight the selected label and optionally hide cells not belonging to the current lineage"""

        highlighted = [
            self.tracks.graph.nodes[node]["tracklet_id"]
            for node in self.selected_nodes
            if self.tracks.get_time(node) == self.viewer.dims.current_step[0]
        ]

        if self.base_label_color_dict is not None:
            colormap = create_selection_label_cmap(
                self.base_label_color_dict,
                visible=visible,
                highlighted=highlighted,
            )
            self.colormap = colormap
