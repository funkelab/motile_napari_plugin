from typing import Any

import numpy as np

from .tracks import Tracks


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
        self.tracks.graph.remove_nodes_from(nodes)
        # TODO: delete the corresponding semgentations, maybe?
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
