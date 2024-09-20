from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from motile_toolbox.candidate_graph import EdgeAttr, NodeAttr
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids
from psygnal import Signal
from spatial_graph import SpatialGraph

if TYPE_CHECKING:
    from typing import Any

    import networkx as nx
    import numpy as np


def _get_nx_location(
    graph: nx.DiGraph,
    node: Any,
    pos_attr=NodeAttr.POS.value,
    time_attr=NodeAttr.TIME.value,
    incl_time: bool = False,
):
    """Get the location of a node in the graph. Optionally include the
    time frame as the first dimension. Raises an error if the node
    is not in the graph.

    Args:
        node (Any): The node id in the graph to get the location of.
        incl_time (bool, optional): If true, include the time as the
            first element of the location array. Defaults to False.

    Returns:
        list[float]: A list holding the location. If the position
            is stored in a single key, the location could be any number
            of dimensions.
    """
    data = graph.nodes[node]
    if isinstance(pos_attr, tuple | list):
        pos = [data[dim] for dim in pos_attr]
    else:
        pos = data[pos_attr]

    if incl_time:
        pos = [data[time_attr], *pos]

    return pos


def nx_graph_to_spatial(graph, time_attr, pos_attr, ndims, segmentation=None):
    if graph.number_of_nodes() != 0:
        try:  # try to get existing track ids
            track_ids = [
                data[NodeAttr.TRACK_ID.value] for _, data in graph.nodes(data=True)
            ]
            max_track_id = max(track_ids)
        except KeyError:
            _, _, max_track_id = assign_tracklet_ids(graph)

    node_attrs = {
        "position": f"double[{ndims}]",
        NodeAttr.TRACK_ID.value: "uint16",
    }
    edge_attrs = {"dummy": "uint8"}

    if segmentation is not None:
        node_seg_attrs = {
            NodeAttr.AREA.value: "double",
            NodeAttr.SEG_ID.value: "uint64",
        }
        edge_seg_attrs = {
            EdgeAttr.IOU.value: "double",
        }
        node_attrs.update(node_seg_attrs)
        edge_attrs.update(edge_seg_attrs)

    sgraph = SpatialGraph(
        ndims=ndims,
        node_dtype="uint64",
        node_attr_dtypes=node_attrs,
        edge_attr_dtypes=edge_attrs,
        position_attr="position",
        directed=True,
    )
    node_ids_map = {node: i for i, node in enumerate(graph.nodes())}
    nx_node_ids = list(node_ids_map.keys())
    sg_node_ids = np.array(list(node_ids_map.values()), dtype="uint64")

    positions = np.array(
        [
            _get_nx_location(graph, node, pos_attr, time_attr, incl_time=True)
            for node in nx_node_ids
        ],
        dtype="double",
    )

    node_dict = {"position": positions}
    for attr in node_attrs:
        if attr == "position":
            continue
        node_dict[attr] = np.array(
            [graph.nodes[node][attr] for node in nx_node_ids], dtype=node_attrs[attr]
        )

    nx_edges = list(graph.edges)
    sg_edges = np.array(
        [[node_ids_map[x] for x in edge] for edge in nx_edges],
        dtype="uint64",
    )
    edge_dict = {}
    for attr in edge_attrs:
        if attr == "dummy":
            edge_dict[attr] = np.ones((len(sg_edges),), dtype="uint8")
        else:
            edge_dict[attr] = np.array([graph.edges[edge][attr] for edge in nx_edges], dtype=edge_attrs[attr])

    sgraph.add_nodes(sg_node_ids, **node_dict)
    sgraph.add_edges(sg_edges, **edge_dict)
    return sgraph, node_ids_map


class Tracks:
    """A set of tracks consisting of a graph and an optional segmentation.
    The graph nodes represent detections and must have a time attribute and
    position attribute. Edges in the graph represent links across time.
    Each node in the graph has a track_id assigned, if it isn't present in the graph already

    Attributes:
        graph (spatial_graph): A graph with nodes representing detections and
            and edges representing links across time. Assumed to be "valid"
            tracks (e.g., this is not supposed to be a candidate graph),
            but the structure is not verified.
        segmentation (Optional(np.ndarray)): An optional segmentation that
            accompanies the tracking graph. If a segmentation is provided,
            it is assumed that the graph has an attribute (default
            "seg_id") holding the segmentation id. Defaults to None.
    """

    refresh = Signal()

    def __init__(
        self,
        graph: SpatialGraph,
        segmentation: np.ndarray | None = None,
        scale: list[float] | None = None,
    ):
        self.graph = graph
        self.segmentation = segmentation
        self.scale = scale
        self.max_track_id = np.max(self.graph.node_attrs[NodeAttr.TRACK_ID.value])

    @classmethod
    def from_nx(cls, graph, time_attr=NodeAttr.TIME.value, pos_attr=NodeAttr.POS.value, ndims=3, segmentation=None, scale=None):
        sg, _ = nx_graph_to_spatial(graph, time_attr, pos_attr, ndims, segmentation=segmentation)
        return cls(sg, segmentation=segmentation, scale=scale)
    
    def get_location(self, node: Any, incl_time: bool = False):
        pos = self.graph.node_attrs[node].position
        if incl_time:
            return pos
        else:
            return pos[1:]

    def get_time(self, node: Any) -> int:
        """Get the time frame of a given node. Raises an error if the node
        is not in the graph.

        Args:
            node (Any): The node id to get the time frame for

        Returns:
            int: The time frame that the node is in
        """
        return self.graph.node_attrs[node].position[0]

    def get_track_id(self, node: Any) -> int:
        """Get the time frame of a given node. Raises an error if the node
        is not in the graph.

        Args:
            node (Any): The node id to get the time frame for

        Returns:
            int: The time frame that the node is in
        """
        return self.graph.node_attrs[node].track_id  # TODO: use NodeAttr again

    def get_area(self, node: Any) -> int | None:
        """Get the area/volume of a given node. Raises an error if the node
        is not in the graph. Returns None if area is not an attribute.

        Args:
            node (Any): The node id to get the area/volume for

        Returns:
            int: The area/volume of the node, or None if the node does not have an area
                attribute
        """
        if NodeAttr.AREA.value in self.graph.node_attr_dtypes:
            return self.graph.node_attrs[node].area  # TODO: use NodeAttr again
        return None

    def get_next_track_id(self) -> int:
        """Get a new track id that is unique from all existing track ids. Does not
        re-use track ids that have been deleted, just increments a counter keeping
        track of the previous maximum.

        Returns:
            int: A new track id that can be used to label a new track
        """
        self.max_track_id += 1
        return self.max_track_id

    def update_segmentation(self, time: int, old_label: int, new_label: int):
        """Update the segmentation in the given time, changing all pixels with old_label
        to new_label.

        Args:
            time (int): The time point to update
            old_label (int): The label to replace
            new_label (int): The new label ID to replace old_label with
        """
        frame = self.segmentation[time]
        mask = frame == old_label
        self.segmentation[time][mask] = new_label
