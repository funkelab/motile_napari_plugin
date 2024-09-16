from __future__ import annotations

from typing import TYPE_CHECKING

from motile_toolbox.candidate_graph import NodeAttr
from pydantic import BaseModel

if TYPE_CHECKING:
    from typing import Any

    import networkx as nx
    import numpy as np


class Tracks(BaseModel):
    """A set of tracks consisting of a graph and an optional segmentation.
    The graph nodes represent detections and must have a time attribute and
    position attribute. Edges in the graph represent links across time.

    Attributes:
        graph (nx.DiGraph): A graph with nodes representing detections and
            and edges representing links across time. Assumed to be "valid"
            tracks (e.g., this is not supposed to be a candidate graph),
            but the structure is not verified.
        segmentation (Optional(np.ndarray)): An optional segmentation that
            accompanies the tracking graph. If a segmentation is provided,
            it is assumed that the graph has an attribute (default
            "seg_id") holding the segmentation id. Defaults to None.
        time_attr (str): The attribute in the graph that specifies the time
            frame each node is in.
        pos_attr (str | tuple[str] | list[str]): The attribute in the graph
            that specifies the position of each node. Can be a single attribute
            that holds a list, or a list of attribute keys.

    """

    graph: nx.DiGraph
    segmentation: np.ndarray | None = None
    time_attr: str = NodeAttr.TIME.value
    pos_attr: str | tuple[str] | list[str] = NodeAttr.POS.value
    scale: list[float] | None = None
    # pydantic does not check numpy arrays
    model_config = {"arbitrary_types_allowed": True}

    def get_location(self, node: Any, incl_time: bool = False):
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
        data = self.graph.nodes[node]
        if isinstance(self.pos_attr, (tuple, list)):
            pos = [data[dim] for dim in self.pos_attr]
        else:
            pos = data[self.pos_attr]

        if incl_time:
            pos = [data[self.time_attr], *pos]

        return pos

    def get_time(self, node: Any) -> int:
        """Get the time frame of a given node. Raises an error if the node
        is not in the graph.

        Args:
            node (Any): The node id to get the time frame for

        Returns:
            int: The time frame that the node is in
        """
        return self.graph.nodes[node][self.time_attr]

    def get_area(self, node: Any) -> int:
        """Get the area/volume of a given node. Raises an error if the node
        is not in the graph. Returns None if area is not an attribute.

        Args:
            node (Any): The node id to get the area/volume for

        Returns:
            int: The area/volume of the node
        """
        
        # Check if the node exists in the graph
        if node not in self.graph.nodes:
            raise ValueError(f"Node {node} is not in the graph.")

        # Return the area attribute if it exists, otherwise None
        return self.graph.nodes[node].get("area")