import copy

import napari
import networkx as nx
import numpy as np
from motile_toolbox.visualization import to_napari_tracks_layer
from napari.utils import CyclicLabelColormap

from motile_plugin.core import Tracks


class TrackGraph(napari.layers.Tracks):
    """Extended tracks layer that holds the track information and emits and responds
    to dynamics visualization signals"""

    def __init__(
        self,
        viewer: napari.Viewer,
        tracks: Tracks,
        name: str,
        colormap: CyclicLabelColormap,
    ):
        graph = nx.DiGraph() if tracks.graph is None else tracks.graph
        track_data, track_props, track_edges = to_napari_tracks_layer(
            graph, frame_key=tracks.time_attr, location_key=tracks.pos_attr
        )

        super().__init__(
            data=track_data,
            graph=track_edges,
            properties=track_props,
            name=name,
            tail_length=3,
            color_by="track_id",
        )

        self.viewer = viewer
        self.colormaps_dict["track_id"] = colormap
        self.colormap = "turbo"  # just to refresh the colormap

        self.tracks_layer_graph = copy.deepcopy(self.graph)  # for restoring graph later

    def update_track_visibility(self, visible: list[int] | str) -> None:
        """Optionally show only the tracks of a current lineage"""

        if visible == "all":
            self.track_colors[:, 3] = 1
            self.graph = self.tracks_layer_graph
        else:
            track_id_mask = np.isin(
                self.properties["track_id"],
                visible,
            )
            self.graph = {
                key: self.tracks_layer_graph[key]
                for key in visible
                if key in self.tracks_layer_graph
            }

            self.track_colors[:, 3] = 0
            self.track_colors[track_id_mask, 3] = 1
            if len(self.graph.items()) == 0:
                self.display_graph = False  # empty dicts to not trigger update (bug?)
                # so disable the graph entirely as a workaround
            else:
                self.display_graph = True
