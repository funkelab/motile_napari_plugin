import copy
from typing import Any

import networkx as nx
import numpy as np
from motile_toolbox.candidate_graph import NodeAttr
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids

from .tracks import Tracks


def relabel_specific_segmentation(
    changed_nodes: list[Any], graph: nx.DiGraph, segmentation: np.array
):
    """Relabel the segmentation for the changed nodes.

    Args:
        nodes (np.ndarray[int]):an array of node ids that have changed
        graph (nx.DiGraph): graph containing the current label values in the SEG_ID
        and the updated label values in the tracklet_id
        segmentations (np.ndarray[int]): A segmentation for each node

    Returns:
        updated_segmentation (np.ndarray[int]): relabeled segmentation
    """

    updated_segmentation = copy.deepcopy(segmentation)
    for node in changed_nodes:
        time_frame = graph.nodes[node][NodeAttr.TIME.value]

        previous_seg_id = graph.nodes[node][NodeAttr.SEG_ID.value]
        tracklet_id = graph.nodes[node]["tracklet_id"]

        # Update SEG_ID to tracklet_id for future use
        graph.nodes[node][NodeAttr.SEG_ID.value] = tracklet_id

        # Get the mask for the specific time_frame and seg_id
        mask = segmentation[time_frame, 0] == previous_seg_id

        # Update the segmentation label
        updated_segmentation[time_frame, 0][mask] = tracklet_id

    return updated_segmentation


class TracksController:
    """A set of high level functions to change the data model.
    All changes to the data should go through this API.
    """

    def __init__(self, tracks: Tracks):
        self.tracks = tracks

    def add_nodes(
        self,
        nodes: np.ndarray[Any],
        attributes: dict[str, np.ndarray],
        segmentations: Any = None,
    ):
        """Add a set of nodes to the tracks. Includes all attributes and the segmentation.

        Args:
            nodes (np.ndarray[int]):an array of node ids
            attributes (dict[str, np.ndarray]): dictionary containing at least time and position attributes
            segmentations (Any, optional): A segmentation for each node (not
                currently implemented). Defaults to None.
        """

        for idx, node in enumerate(nodes):
            attrs = {attr: val[idx] for attr, val in attributes.items()}
            self.tracks.graph.add_node(node, **attrs)
        # TODO: Implement segmentations
        self.tracks.refresh.emit()

    def delete_nodes(self, nodes: np.ndarray[Any]):
        """_summary_

        Args:
            nodes (np.ndarray): _description_
        """

        # if we have a segmentation, first check which labels should be converted to zero
        if self.tracks.segmentation is not None:
            for node in nodes:
                time_frame = self.tracks.graph.nodes[node][NodeAttr.TIME.value]
                current_track_id = self.tracks.graph.nodes[node]["tracklet_id"]
                mask = self.tracks.segmentation[time_frame, 0] == current_track_id
                self.tracks.segmentation[time_frame, 0][mask] = (
                    0  # remove from the segmentation
                )

        # store the current node:tracklet_id dictionary
        prev_tracklet_dict = {
            node: data["tracklet_id"]
            for node, data in self.tracks.graph.nodes(data=True)
            if "tracklet_id" in data
        }

        # remove nodes from the graph
        self.tracks.graph.remove_nodes_from(nodes)

        # reassign tracklet ids
        self.tracks.graph, _ = assign_tracklet_ids(self.tracks.graph)

        if self.tracks.segmentation is not None:
            # check which tracklet_ids have changed
            new_tracklet_dict = {
                node: data["tracklet_id"]
                for node, data in self.tracks.graph.nodes(data=True)
                if "tracklet_id" in data
            }
            changed_nodes = [
                node
                for node in new_tracklet_dict
                if node in prev_tracklet_dict
                and prev_tracklet_dict[node] != new_tracklet_dict[node]
            ]

            self.tracks.segmentation = relabel_specific_segmentation(
                changed_nodes=changed_nodes,
                graph=self.tracks.graph,
                segmentation=self.tracks.segmentation,
            )

        self.tracks.refresh.emit()

    def update_nodes(self, nodes: np.ndarray[Any], attributes: dict[str, np.ndarray]):
        pass

    def add_edges(self, edges: np.ndarray[int], attributes: dict[str, np.ndarray]):
        """Add edges and attributes to the graph

        Args:
            edges (np.array[int]): An Nx2 array of N edges, each with source and target node ids
            attributes (dict[str, np.ndarray]): dictionary mapping attribute names to
                an array of values, where the index in the array matches the edge index
        """
        for idx, edge in enumerate(edges):
            attrs = {attr: val[idx] for attr, val in attributes.items()}
            self.tracks.graph.add_edge(edge, **attrs)
        # TODO: Implement segmentations
        self.tracks.refresh.emit()

    def delete_edges(self, edges: np.ndarray):
        """Delete edges from the graph.

        Args:
            edges (np.ndarray): _description_
        """
        self.tracks.graph.remove_edges_from(edges)
        # TODO: update tracklet IDs?
        self.tracks.refresh.emit()

    def update_edges(self, edges: np.ndarray[int], attributes: np.ndarray):
        pass

    def update_segmentations(self, nodes: np.ndarray[int], updated_values: Any):
        pass

    def add_node_attribute(self, name: str, values: any):
        pass

    def add_edge_attribute(self, name: str, values: any):
        pass

    def remove_node_attribute(self, name: str):
        pass
