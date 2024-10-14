from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids

from .tracks import Tracks

if TYPE_CHECKING:
    import numpy as np

    from .tracks import Node


class SolutionTracks(Tracks):
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

        self.max_track_id = self.max_track_id + 1
        return self.max_track_id

    def get_track_id(self, node) -> int:
        track_id = self._get_node_attr(node, NodeAttr.TRACK_ID.value, required=True)
        return track_id

    def set_track_id(self, node: Node, value: int):
        self._set_node_attr(node, NodeAttr.TRACK_ID.value, value)

    def _initialize_track_ids(self):
        if self.graph.number_of_nodes() != 0:
            if len(self.node_id_to_track_id) < self.graph.number_of_nodes():
                # not all nodes have a track id: reassign
                _, _, self.max_track_id = assign_tracklet_ids(self.graph)
            else:
                self.max_track_id = max(self.node_id_to_track_id.values())
        else:
            self.max_track_id = 0
