from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional, TypeVar

import networkx as nx
import numpy as np
from motile_toolbox.candidate_graph import NodeAttr
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids
from psygnal import Signal

if TYPE_CHECKING:
    from pathlib import Path

Node = TypeVar("Node", bound=Any)
Edge = TypeVar("Edge", bound=tuple[Node, Node])
Attributes = TypeVar("Attributes", bound=dict[str, np.ndarray])


class Tracks:
    """A set of tracks consisting of a graph and an optional segmentation.
    The graph nodes represent detections and must have a time attribute and
    position attribute. Edges in the graph represent links across time.
    Each node in the graph has a track_id assigned, if it isn't present in the graph already

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

    refresh: Signal[Optional[str]] = Signal()
    GRAPH_FILE = "graph.json"
    SEG_FILE = "seg.npy"
    ATTRS_FILE = "attrs.json"

    def __init__(
        self,
        graph: nx.DiGraph,
        segmentation: np.ndarray | None = None,
        time_attr: str = NodeAttr.TIME.value,
        pos_attr: str | tuple[str] | list[str] = NodeAttr.POS.value,
        scale: list[float] | None = None,
    ):
        self.graph = graph
        self.segmentation = segmentation
        self.time_attr = time_attr
        self.pos_attr = pos_attr
        self.scale = scale

        if graph.number_of_nodes() != 0:
            self.create_node_id_to_track_id()
        else:
            self.node_id_to_track_id = {}
            self.max_track_id = 0

    # pydantic does not check numpy arrays
    model_config = {"arbitrary_types_allowed": True}

    def create_node_id_to_track_id(self) -> None:
        """Create a dictionary mapping the node_id to the tracklet_id, and specify the max_track_id"""

        self.node_id_to_track_id = {}
        try:  # try to get existing track ids
            for node, data in self.graph.nodes(data=True):
                self.node_id_to_track_id[node] = data[NodeAttr.TRACK_ID.value]
            self.max_track_id = max(self.node_id_to_track_id.values())
        except KeyError:
            _, _, self.max_track_id = assign_tracklet_ids(self.graph)
            for node, data in self.graph.nodes(data=True):
                self.node_id_to_track_id[node] = data[NodeAttr.TRACK_ID.value]

    def get_location(self, node: Any, incl_time: bool = False) -> list:
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
        if isinstance(self.pos_attr, tuple | list):
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

    def get_track_id(self, node: Any) -> int:
        """Get the time frame of a given node. Raises an error if the node
        is not in the graph.

        Args:
            node (Any): The node id to get the time frame for

        Returns:
            int: The time frame that the node is in
        """
        return self.graph.nodes[node][NodeAttr.TRACK_ID.value]

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

    def get_next_track_id(self) -> int:
        """Return the next available track_id and update self.max_track_id"""

        self.max_track_id = max(self.node_id_to_track_id.values()) + 1
        return self.max_track_id

    def change_segmentation_label(self, time, old_label, new_label):
        """Updates old_label to new_label in the segmentation at frame time."""

        frame = self.segmentation[time]
        mask = frame == old_label
        self.segmentation[time][mask] = new_label

    def set_pixels(self, pixels: tuple[np.ndarray, ...], value: int):
        """Set the given pixels in the segmentation to the given value.

        Args:
            pixels (tuple[np.ndarray]): The pixels that should be set to the value,
                formatted like the output of np.nonzero (each element of the tuple
                represents one dimension, containing an array of indices in that dimension).
                Can be used to directly index the segmentation.
            value (int): The value to set each pixel to
        """
        self.segmentation[pixels] = value

    def get_pixels(self, nodes: list[Node]) -> list[tuple[np.ndarray, ...]] | None:
        """Get the pixels corresponding to each node in the nodes list.

        Args:
            nodes (list[Node]): A list of node to get the values for.

        Returns:
            list[tuple[np.ndarray, ...]] | None: A list of tuples, where each tuple
            represents the pixels for one of the input nodes, or None if the segmentation
            is None. The tuple will have length equal to the number of segmentation
            dimensions, and can be used to index the segmentation.
        """
        if self.segmentation is None:
            return None
        pix_list = []
        for node in nodes:
            track_id = self.get_track_id(node)
            time = self.get_time(node)
            loc_pixels = np.nonzero(self.segmentation[time] == track_id)
            time_array = np.ones_like(loc_pixels[0]) * time
            pix_list.append((time_array, *loc_pixels))
        return pix_list

    def update_segmentation(self, updated_pixels: list) -> None:
        """Updates the pixels at given indices to the new values

        Args:
            updated_pixels (list[(tuple(np.ndarray, np.ndarray, np.ndarray), np.ndarray, int|np.ndarray])):
                A list of len 3 tuples with paint event 'atoms'.
                The first element is a tuple of np.ndarrays with involved indices for each dimension.
                The second element is an array of the previous values at these indices (not used here).
                The last element is an integer or np.ndarray with the new values.
        """

        for prev_indices, _, next_values in reversed(
            updated_pixels
        ):  # reversed because a paint event has to be undone in reversed order,
            # and we do not need to ever 'forward apply' the paint event because that is handled in the napari layer
            if len(prev_indices) == len(self.segmentation.shape):
                self.segmentation[prev_indices] = next_values
            elif (
                len(prev_indices) == len(self.segmentation.shape) - 1
            ):  # this is because the events coming from the segmentation do not have the extra dimension the tracks.segmentaton has
                self.segmentation[(prev_indices[0], 0) + prev_indices[1:]] = next_values
            else:
                raise ValueError(
                    f"Indices have the wrong length: {len(prev_indices)}, while the segmentation shape has length {len(self.segmentation.shape)}"
                )

    def set_node_attributes(self, nodes: list[Node], attributes: Attributes):
        """Update the attributes for given nodes"""

        for idx, node in enumerate(nodes):
            if node in self.graph:
                for key, values in attributes.items():
                    self.graph.nodes[node][key] = values[idx]
            else:
                print(f"Node {node} not found in the graph.")

    def get_node_attributes(self, nodes: list[Node]) -> dict:
        """Return the attributes for given nodes"""

        attributes = {}
        for node in nodes:
            if node in self.graph:
                data = self.graph.nodes[node]
                for key, value in data.items():
                    vals = attributes.get(key, [])
                    vals.append(value)
                    attributes[key] = vals
        return attributes

    def get_edge_attributes(self, edges: list[Edge]) -> dict:
        """Return the attributes for given edges"""

        attributes = {}
        for edge in edges:
            if self.graph.has_edge(*edge):
                data = self.graph.edges[edge]
                for key, value in data.items():
                    vals = attributes.get(key, [])
                    vals.append(value)
                    attributes[key] = vals
        return attributes

    def set_edge_attributes(self, edges: list[Edge], attributes: Attributes) -> None:
        """Set the edge attributes for the given edges. Attributes should already exist
        (although adding will work in current implementation, they cannot currently be
        removed)

        Args:
            edges (list[Edge]): A list of edges to set the attributes for
            attributes (Attributes): A dictionary of attribute name -> numpy array,
                where the length of the arrays matches the number of edges.
                Attributes should already exist: this function will only
                update the values.
        """
        for idx, edge in enumerate(edges):
            if self.graph.has_edge(*edge):
                for key, value in attributes.items():
                    self.graph.edges[edge][key] = value[idx]
            else:
                print(f"Edge {edge} not found in the graph.")

    def save(self, directory: Path):
        """Save the tracks to the given directory.
        Currently, saves the graph as a json file in networkx node link data format,
        saves the segmentation as a numpy npz file, and saves the time and position
        attributes and scale information in an attributes json file.

        Args:
            directory (Path): The directory to save the tracks in.
        """
        self._save_graph(directory)
        if self.segmentation is not None:
            self._save_seg(directory)
        self._save_attrs(directory)

    def _save_graph(self, directory: Path):
        """Save the graph to file. Currently uses networkx node link data
        format (and saves it as json).

        Args:
            directory (Path): The directory in which to save the graph file.
        """
        graph_file = directory / self.GRAPH_FILE
        with open(graph_file, "w") as f:
            json.dump(nx.node_link_data(self.graph), f)

    def _save_seg(self, directory: Path):
        """Save a segmentation as a numpy array using np.save. In the future,
        could be changed to use zarr or other file types.

        Args:
            directory (Path): The directory in which to save the segmentation
        """
        out_path = directory / self.SEG_FILE
        np.save(out_path, self.segmentation)

    def _save_attrs(self, directory: Path):
        """Save the time_attr, pos_attr, and scale in a json file in the given directory.

        Args:
            directory (Path):  The directory in which to save the attributes
        """
        out_path = directory / self.ATTRS_FILE
        attrs_dict = {
            "time_attr": self.time_attr,
            "pos_attr": self.pos_attr,
            "scale": self.scale,
        }
        with open(out_path, "w") as f:
            json.dump(attrs_dict, f)

    @classmethod
    def load(cls, directory: Path, seg_required=False) -> Tracks:
        """Load a Tracks object from the given directory. Looks for files
        in the format generated by Tracks.save.

        Args:
            directory (Path): The directory containing tracks to load
            seg_required (bool, optional): If true, raises a FileNotFoundError if the
                segmentation file is not present in the directory. Defaults to False.

        Returns:
            Tracks: A tracks object loaded from the given directory
        """
        graph_file = directory / cls.GRAPH_FILE
        graph = cls._load_graph(graph_file)

        seg_file = directory / cls.SEG_FILE
        seg = cls._load_seg(seg_file, seg_required=seg_required)

        attrs_file = directory / cls.ATTRS_FILE
        attrs = cls._load_attrs(attrs_file)

        return cls(graph, seg, **attrs)

    @staticmethod
    def _load_graph(graph_file: Path) -> nx.DiGraph:
        """Load the graph from the given json file. Expects networkx node_link_graph
        formatted json.

        Args:
            graph_file (Path): The json file to load into a networkx graph

        Raises:
            FileNotFoundError: If the file does not exist

        Returns:
            nx.DiGraph: A networkx graph loaded from the file.
        """
        if graph_file.is_file():
            with open(graph_file) as f:
                json_graph = json.load(f)
            return nx.node_link_graph(json_graph, directed=True)
        else:
            raise FileNotFoundError(f"No graph at {graph_file}")

    @staticmethod
    def _load_seg(seg_file: Path, seg_required: bool = False) -> np.ndarray | None:
        """Load a segmentation from a file. If the file doesn't exist, either return
        None or raise a FileNotFoundError depending on the seg_required flag.

        Args:
            seg_file (Path): The npz file to load.
            seg_required (bool, optional): If true, raise a FileNotFoundError if the
                segmentation is not present. Defaults to False.

        Returns:
            np.ndarray | None: The segmentation array, or None if it wasn't present and
                seg_required was False.
        """
        if seg_file.is_file():
            return np.load(seg_file)
        elif seg_required:
            raise FileNotFoundError(f"No segmentation at {seg_file}")
        else:
            return None

    @staticmethod
    def _load_attrs(attrs_file: Path) -> dict:
        if attrs_file.is_file():
            with open(attrs_file) as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"No attributes at {attrs_file}")

    @classmethod
    def delete(cls, directory: Path):
        # Lets be safe and remove the expected files and then the directory
        (directory / cls.GRAPH_FILE).unlink()
        (directory / cls.SEG_FILE).unlink()
        (directory / cls.ATTRS_FILE).unlink()
        directory.rmdir()
