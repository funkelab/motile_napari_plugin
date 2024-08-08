import copy

import napari
import networkx as nx
import numpy as np
from motile_toolbox.visualization import to_napari_tracks_layer
from napari.utils import CyclicLabelColormap


class TrackGraph(napari.layers.Tracks):
    """Extended points layer that holds the track information and emits and responds to dynamics visualization signals"""

    def __init__(
        self,
        viewer: napari.Viewer,
        data: nx.DiGraph,
        name: str,
        colormap: CyclicLabelColormap,
        scale: np.array,
    ):
        track_data, track_props, track_edges = to_napari_tracks_layer(data)

        super().__init__(
            data=track_data,
            graph=track_edges,
            properties=track_props,
            name=name,
            tail_length=3,
            color_by="track_id",
            scale=scale,
        )

        self.viewer = viewer
        self.colormaps_dict["track_id"] = colormap
        self.visible_tracks = "all"
        self.visible_plane_tracks = "all"
        self.blending = "translucent_no_depth"

        self.tracks_layer_graph = copy.deepcopy(
            self.graph
        )  # for restoring graph later

    def update_track_visibility(
        self,
        visible: list[int] | str | None = None,
        plane_nodes: list[int] | str | None = None,
    ) -> None:
        """Optionally show only the tracks of a current lineage"""

        if visible is not None:
            self.visible_tracks = visible
        if plane_nodes is not None:
            self.visible_plane_tracks = plane_nodes

        if isinstance(self.visible_tracks, str) and isinstance(
            self.visible_plane_tracks, str
        ):
            visible = "all"
        elif not isinstance(self.visible_tracks, str) and isinstance(
            self.visible_plane_tracks, str
        ):
            visible = self.visible_tracks
        elif isinstance(self.visible_tracks, str) and not isinstance(
            self.visible_plane_tracks, str
        ):
            visible = self.visible_plane_tracks
        else:
            visible = list(
                set(self.visible_tracks).intersection(
                    set(self.visible_plane_tracks)
                )
            )

        if isinstance(visible, str):
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
                self.display_graph = False  # empty dicts to not trigger update (bug?) so disable the graph entirely as a workaround
            else:
                self.display_graph = True

        self.events.rebuild_tracks()  # fire the event to update the colors
