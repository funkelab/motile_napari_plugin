from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr

from .tracks import Tracks

if TYPE_CHECKING:
    from pathlib import Path

    import numpy as np

    from .tracks import Node


class SolutionTracks(Tracks):
    """Difference from Tracks: every node must have a track_id"""

    def __init__(
        self,
        graph: nx.DiGraph,
        segmentation: np.ndarray | None = None,
        time_attr: str = NodeAttr.TIME.value,
        pos_attr: str | tuple[str] | list[str] = NodeAttr.POS.value,
        scale: list[float] | None = None,
        ndim: int | None = None,
    ):
        super().__init__(
            graph,
            segmentation=segmentation,
            time_attr=time_attr,
            pos_attr=pos_attr,
            scale=scale,
            ndim=ndim,
        )
        self.max_track_id: int
        self._initialize_track_ids()

    @classmethod
    def from_tracks(cls, tracks: Tracks):
        return cls(
            tracks.graph,
            segmentation=tracks.segmentation,
            time_attr=tracks.time_attr,
            pos_attr=tracks.pos_attr,
            scale=tracks.scale,
            ndim=tracks.ndim,
        )

    @property
    def node_id_to_track_id(self) -> dict[Node, int]:
        return nx.get_node_attributes(self.graph, NodeAttr.TRACK_ID.value)

    def get_next_track_id(self) -> int:
        """Return the next available track_id and update self.max_track_id"""
        computed_max = max(self.node_id_to_track_id.values())
        if self.max_track_id < computed_max:
            self.max_track_id = computed_max
        self.max_track_id = self.max_track_id + 1
        return self.max_track_id

    def get_track_id(self, node) -> int:
        track_id = self._get_node_attr(node, NodeAttr.TRACK_ID.value, required=True)
        return track_id

    def set_track_id(self, node: Node, value: int):
        self._set_node_attr(node, NodeAttr.TRACK_ID.value, value)

    def _initialize_track_ids(self):
        self.max_track_id = 0
        self.track_id_to_node = {}

        if self.graph.number_of_nodes() != 0:
            if len(self.node_id_to_track_id) < self.graph.number_of_nodes():
                # not all nodes have a track id: reassign
                self._assign_tracklet_ids()
            else:
                self.max_track_id = max(self.node_id_to_track_id.values())
                for node, track_id in self.node_id_to_track_id.items():
                    if track_id not in self.track_id_to_node:
                        self.track_id_to_node[track_id] = []
                    self.track_id_to_node[track_id].append(node)

    def _assign_tracklet_ids(self):
        """Add a track_id attribute to a graph by removing division edges,
        assigning one id to each connected component.
        Also sets the max_track_id and initializes a dictionary from track_id to nodes
        """
        graph_copy = self.graph.copy()

        parents = [node for node, degree in self.graph.out_degree() if degree >= 2]
        intertrack_edges = []

        # Remove all intertrack edges from a copy of the original graph
        for parent in parents:
            daughters = [child for p, child in self.graph.out_edges(parent)]
            for daughter in daughters:
                graph_copy.remove_edge(parent, daughter)
                intertrack_edges.append((parent, daughter))

        track_id = 1
        for tracklet in nx.weakly_connected_components(graph_copy):
            nx.set_node_attributes(
                self.graph,
                {node: {NodeAttr.TRACK_ID.value: track_id} for node in tracklet},
            )
            track_id += 1
        self.max_track_id = track_id - 1

    def export_tracks(self, outfile: Path | str):
        """Export the tracks from this run to a csv with the following columns:
        t,[z],y,x,id,parent_id,track_id
        Cells without a parent_id will have an empty string for the parent_id.
        Whether or not to include z is inferred from self.ndim
        """
        header = ["t", "z", "y", "x", "id", "parent_id", "track_id"]
        if self.ndim == 3:
            header = [header[0]] + header[2:]  # remove z
        with open(outfile, "w") as f:
            f.write(",".join(header))
            for node_id in self.graph.nodes():
                parents = list(self.graph.predecessors(node_id))
                parent_id = "" if len(parents) == 0 else parents[0]
                track_id = self.get_track_id(node_id)
                time = self.get_time(node_id)
                position = self.get_position(node_id)
                row = [
                    time,
                    *position,
                    node_id,
                    parent_id,
                    track_id,
                ]
                f.write("\n")
                f.write(",".join(map(str, row)))
