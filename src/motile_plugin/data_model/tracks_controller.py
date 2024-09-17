from typing import Any, Optional

import numpy as np

from .tracks import Tracks


class TracksController:
    """A set of high level functions to change the data model.
    All changed to the data should go through this API.
    """

    def __init__(self, tracks: Tracks):
        self.tracks = tracks

    def add_nodes(
        nodes: np.ndarray,
        attributes: np.ndarray,
        segmentations: Optional[np.ndarray] = None,
    ):
        """_summary_

        Args:
            nodes (np.ndarray): _description_
            attributes (np.ndarray): _description_
            segmentations (np.ndarray | None, optional): _description_. Defaults to None.
        """
        # TODO: Implement in minimal editing example

    def delete_nodes(nodes: np.ndarray):
        """_summary_

        Args:
            nodes (np.ndarray): _description_
        """

        # TODO: Implement in minimal editing example

    def update_nodes(nodes: np.ndarray, attributes: np.ndarray):
        pass

    def add_edges(edges: np.array, attributes: np.ndarray):
        # TODO: Implement in minimal editing example
        pass

    def delete_edges(edges: np.ndarray):
        # TODO: Implement in minimal editing example
        pass

    def update_edges(edges: np.ndarray, attributes: np.ndarray):
        pass

    def update_segmentations(nodes: np.ndarray, updated_values: Any):
        pass

    def add_node_attribute(name: str, values: any):
        pass

    def add_edge_attribute(name: str, values: any):
        pass

    def remove_node_attribute(name: str):
        pass
