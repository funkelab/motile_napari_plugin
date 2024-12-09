from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import napari
import numpy as np

if TYPE_CHECKING:
    from motile_tracker.data_model.solution_tracks import SolutionTracks
    from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer


def update_napari_tracks(
    tracks: SolutionTracks,
):
    """Function to take a networkx graph with assigned track_ids and return the data needed to add to
    a napari tracks layer.

    Args:
        tracks (SolutionTracks): tracks that have track_ids and have a tree structure

    Returns:
        data: array (N, D+1)
            Coordinates for N points in D+1 dimensions. ID,T,(Z),Y,X. The first
            axis is the integer ID of the track. D is either 3 or 4 for planar
            or volumetric timeseries respectively.
        graph: dict {int: list}
            Graph representing associations between tracks. Dictionary defines the
            mapping between a track ID and the parents of the track. This can be
            one (the track has one parent, and the parent has >=1 child) in the
            case of track splitting, or more than one (the track has multiple
            parents, but only one child) in the case of track merging.
    """

    ndim = tracks.ndim - 1
    graph = tracks.graph
    napari_data = np.zeros((graph.number_of_nodes(), ndim + 2))
    napari_edges = {}

    parents = [node for node, degree in graph.out_degree() if degree >= 2]
    intertrack_edges = []

    # Remove all intertrack edges from a copy of the original graph
    graph_copy = graph.copy()
    for parent in parents:
        daughters = [child for _, child in graph.out_edges(parent)]
        for daughter in daughters:
            graph_copy.remove_edge(parent, daughter)
            intertrack_edges.append((parent, daughter))

    for index, node in enumerate(graph.nodes(data=True)):
        node_id, data = node
        location = tracks.get_position(node_id)
        napari_data[index] = [
            tracks.get_track_id(node_id),
            tracks.get_time(node_id),
            *location,
        ]

    for parent, child in intertrack_edges:
        parent_track_id = tracks.get_track_id(parent)
        child_track_id = tracks.get_track_id(child)
        if child_track_id in napari_edges:
            napari_edges[child_track_id].append(parent_track_id)
        else:
            napari_edges[child_track_id] = [parent_track_id]

    return napari_data, napari_edges


class TrackGraph(napari.layers.Tracks):
    """Extended tracks layer that holds the track information and emits and responds
    to dynamics visualization signals"""

    def __init__(
        self,
        name: str,
        tracks_viewer: TracksViewer,
    ):
        self.tracks_viewer = tracks_viewer
        track_data, track_edges = update_napari_tracks(
            self.tracks_viewer.tracks,
        )

        super().__init__(
            data=track_data,
            graph=track_edges,
            name=name,
            tail_length=3,
            color_by="track_id",
        )

        self.colormaps_dict["track_id"] = self.tracks_viewer.colormap
        self.tracks_layer_graph = copy.deepcopy(self.graph)  # for restoring graph later
        self.colormap = "turbo"  # just to 'refresh' the track_id colormap, we do not actually use turbo

    def _refresh(self):
        """Refreshes the displayed tracks based on the graph in the current tracks_viewer.tracks"""

        track_data, track_edges = update_napari_tracks(
            self.tracks_viewer.tracks,
        )

        self.data = track_data
        self.graph = track_edges
        self.tracks_layer_graph = copy.deepcopy(self.graph)
        self.colormaps_dict["track_id"] = self.tracks_viewer.colormap
        self.colormap = "turbo"  # just to 'refresh' the track_id colormap, we do not actually use turbo

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
                self.display_graph = False  # empty dicts to not trigger update (bug?) so disable the graph entirely as a workaround
            else:
                self.display_graph = True
