from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional, TypeAlias

import networkx as nx
import numpy as np
from motile_toolbox.candidate_graph import EdgeAttr, NodeAttr
from motile_toolbox.candidate_graph.iou import _compute_ious
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids
from psygnal import Signal
from skimage import measure

if TYPE_CHECKING:
    from pathlib import Path

Node: TypeAlias = Any
Edge: TypeAlias = tuple[Node, Node]
Attributes: TypeAlias = dict[str, np.ndarray]
SegMask: TypeAlias = tuple[np.ndarray, ...]


class Tracks:
    """A set of tracks consisting of a graph and an optional segmentation.
    The graph nodes represent detections and must have a time attribute and
    position attribute. Edges in the graph represent links across time.
    Each node in the graph has a track_id assigned, if it isn't present in the graph already
    TODO: remove track_ids from the generic data structure, to allow candidate graphs

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

    refresh = Signal(Optional[str])
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
        self.scale = scale  # TODO: everything breaks if scale is NOne

        self.seg_managed_node_attrs = (self.pos_attr, NodeAttr.AREA.value)
        self.seg_managed_edge_attrs = (EdgeAttr.IOU.value,)

        if graph.number_of_nodes() != 0:
            if len(self.node_id_to_track_id) < self.graph.number_of_nodes():
                # not all nodes have a track id: reassign
                _, _, self.max_track_id = assign_tracklet_ids(self.graph)
            else:
                self.max_track_id = max(self.node_id_to_track_id.values())
            self.seg_time_to_node = self._create_seg_time_to_node()
        else:
            self.max_track_id = 0
            self.seg_time_to_node: dict[dict[int, Node]] = {}

    def _create_seg_time_to_node(self) -> dict[dict[int, Node]]:
        """Create a dictionary mapping seg_id -> dict(time_point -> node_id)"""
        seg_time_to_node: dict[dict[int, Node]] = {}
        if self.segmentation is None:
            return seg_time_to_node

        for node in self.graph.nodes():
            seg_id = self.get_seg_id(node)
            if seg_id not in seg_time_to_node:
                seg_time_to_node[seg_id] = {}
            time = self.get_time(node)
            seg_time_to_node[seg_id][time] = node
        return seg_time_to_node

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

    def get_node_attribute(self, node: Any, attr: str) -> int:
        """Get the attribute of a given node. Raises an error if the node
        is not in the graph.

        Args:
            node (Any): The node id to get the time frame for

        Returns:
            int: The time frame that the node is in
        """
        return self.graph.nodes[node][attr]

    def get_seg_id(self, node: Any) -> int | None:
        """Get the segmentation id of a given node. Raises a KeyError if the node
        is not in the graph. Returns None if the node does not have an associated
        segmentation.

        Args:
            node (Any): The node id to get the seg id of

        Returns:
            int | None: The seg id of the node, or None if the node does not have a
            segmentation
        """
        return self.graph.nodes[node].get(NodeAttr.SEG_ID.value, None)

    def get_track_id(self, node: Any) -> int | None:
        """Get the track id of a given node. Raises a KeyError if the node
        is not in the graph. Returns None if the node does not have an associated
        segmentation.

        Args:
            node (Any): The node id to get the seg id of

        Returns:
            int | None: The seg id of the node, or None if the node does not have a
            segmentation
        """
        return self.graph.nodes[node].get(NodeAttr.TRACK_ID.value, None)

    def set_track_id(self, node: Any, track_id: int) -> int | None:
        """Get the track id of a given node. Raises a KeyError if the node
        is not in the graph. Returns None if the node does not have an associated
        segmentation.

        Args:
            node (Any): The node id to get the seg id of

        Returns:
            int | None: The seg id of the node, or None if the node does not have a
            segmentation
        """
        self.graph.nodes[node][NodeAttr.TRACK_ID.value] = track_id

    def set_seg_id(self, node: Node, seg_id: int) -> None:
        """Set the segmentation id attribute for a given node, and update
        the internal mappings. Does not update the segmentation, if present.
        Args:
            node (Node): The node id to set the seg_id of
            seg_id (int): The segmentation id to set the attribute to
        """
        time = self.get_time(node)
        old_id = self.graph.nodes[node].get(NodeAttr.SEG_ID.value)
        if old_id is not None and old_id in self.seg_time_to_node:
            del self.seg_time_to_node[old_id][time]
        self.graph.nodes[node][NodeAttr.SEG_ID.value] = seg_id
        if seg_id not in self.seg_time_to_node:
            self.seg_time_to_node[seg_id] = {}
        self.seg_time_to_node[seg_id][time] = node

    def remove_node(self, node: Node):
        """Remove the node from the graph and update the internal mappings.
        Does not update the segmentation if present.

        Args:
            node (Node): The node to remove from the graph
        """
        time = self.get_time(node)
        old_id = self.get_seg_id(node)
        if old_id is not None:
            del self.seg_time_to_node[old_id][time]
        self.graph.remove_node(node)

    def add_node(
        self,
        node: Node,
        time: int,
        position: Any | None = None,
        seg_id: int | None = None,
        attrs: dict[str, Any] | None = None,
    ):
        """Add a node to the graph. Will update the internal mappings and generate the
        segmentation-controlled attributes if there is a segmentation present.
        The segmentation should have been previously updated, otherwise the
        attributes will not update properly.

        Args:
            node (Node): The node id to add
            time (int): the time frame of the node to add
            position (Any | None): The spatial position of the node (excluding time).
                Can be None if it should be automatically detected from the segmentation.
                Either seg_id or position must be provided. Defaults to None.
            seg_id (int | None): The segmentation id of the node, used to match the node
                to the segmentation at the given time, or None if the node does not have
                a matching segmentation. Either seg_id or position must be provided.
                Defaults to None.
            attrs (dict[str, Any] | None, optional): A dictionary of additional
                attributes for the node, or None if there are no additional attributes.
                Attributes with the same name as "controlled" attributes will be
                overwritten. Defaults to None
        """
        if attrs is None:
            attrs = {}
        attrs[self.time_attr] = time
        attrs[self.pos_attr] = position
        if self.segmentation is not None:
            attrs.update(self._compute_node_attrs(seg_id, time))
        assert (
            attrs[self.pos_attr] is not None
        ), f"Unknown position for node {node} in time {time} with seg_id {seg_id}"
        self.graph.add_node(node, **attrs)
        if seg_id not in self.seg_time_to_node:
            self.seg_time_to_node[seg_id] = {}
        self.seg_time_to_node[seg_id][time] = node

    def _compute_node_attrs(self, seg_id: int, time: int) -> dict[str, Any]:
        """Get the segmentation controlled node attributes (area and position)
        from the segmentation with label seg_id in the given time point.

        Args:
            seg_id (int): The label id to query the current segmentation for
            time (int): The time frame of the current segmentation to query

        Returns:
            dict[str, int]: A dictionary containing the attributes that could be
                determined from the segmentation. It will be empty if self.segmentation
                is None. If self.segmentation exists but seg_id is not present in time,
                area will be 0 and position will not be included. If self.segmentation
                exists and seg_id is present in time, area and position will be included.
        """
        attrs = {}
        if self.segmentation is None:
            return attrs
        seg = self.segmentation[time][0] == seg_id
        area = np.sum(seg)
        if self.scale is not None:
            area *= np.prod(self.scale)
        attrs[NodeAttr.AREA.value] = area
        if area > 0:
            # only include the position if the segmentation was actually there
            pos = measure.centroid(seg, spacing=self.scale)
            attrs[self.pos_attr] = pos
        return attrs

    def add_edge(self, edge: Edge, attrs: dict[str, Any] | None = None):
        if attrs is None:
            attrs = {}
        attrs.update(self._compute_edge_attrs(edge))
        self.graph.add_edge(edge[0], edge[1], **attrs)

    def _compute_edge_attrs(self, edge: Edge) -> dict[str, Any]:
        """Get the segmentation controlled edge attributes (IOU)
        from the segmentations associated with the endpoints of the edge.
        The endpoints should already exist and have associated segmentations.

        Args:
            edge (Edge): The edge to compute the segmentation-based attributes from

        Returns:
            dict[str, int]: A dictionary containing the attributes that could be
                determined from the segmentation. It will be empty if self.segmentation
                is None or if self.segmentation exists but the endpoint segmentations
                are not found.
        """
        attrs = {}
        source, target = edge
        source_seg = self.get_seg_id(source)
        target_seg = self.get_seg_id(target)
        if self.segmentation is None or source_seg is None or target_seg is None:
            return attrs
        source_time = self.get_time(source)
        target_time = self.get_time(target)

        source_arr = self.segmentation[source_time][0] == source_seg
        target_arr = self.segmentation[target_time][0] == target_seg

        iou_list = _compute_ious(source_arr, target_arr)  # list of (id1, id2, iou)
        iou = 0 if len(iou_list) == 0 else iou_list[0][2]

        attrs[EdgeAttr.IOU.value] = iou
        return attrs

    def get_node(self, seg_id: int, time: int) -> Node | None:
        """Get the node with the given segmentation ID in the given time point.
        Useful for going from segmentation labels to graph nodes.

        Args:
            seg_id (int): The segmentation id of the node
            time (int): the time point of the node

        Returns:
            Node | None: the node id with the given seg_id in the given time, or None
                if no such node exists.
        """
        return self.seg_time_to_node.get(seg_id, {}).get(time, None)

    @property
    def node_id_to_track_id(self) -> dict[Node, int]:
        return nx.get_node_attributes(self.graph, NodeAttr.TRACK_ID.value)

    def get_area(self, node: Node) -> int:
        """Get the area/volume of a given node. Raises a KeyError if the node
        is not in the graph. Returns None if the given node does not have an Area
        attribute.

        Args:
            node (Node): The node id to get the area/volume for

        Returns:
            int: The area/volume of the node
        """
        return self.graph.nodes[node].get("area")

    def get_next_track_id(self) -> int:
        """Return the next available track_id and update self.max_track_id"""

        self.max_track_id = self.max_track_id + 1
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
        if len(pixels) < len(self.segmentation.shape):
            # add dummy hypothesis dimension
            pixels = (pixels[0], np.zeros_like(pixels[0]), *pixels[1:])
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
            loc_pixels = np.nonzero(self.segmentation[time][0] == track_id)
            time_array = np.ones_like(loc_pixels[0]) * time
            pix_list.append((time_array, *loc_pixels))
        return pix_list

    def update_segmentation(self, node: Node, pixels: SegMask, added=True) -> None:
        """Updates the segmentation of the given node. Also updates the
        auto-computed attributes of the node and incident edges.
        """
        time = self.get_time(node)
        seg_id = self.get_seg_id(node)
        value = seg_id if added else 0
        self.set_pixels(pixels, value)
        new_node_attrs = self._compute_node_attrs(seg_id, time)
        new_node_attrs = {attr: [val] for attr, val in new_node_attrs.items()}
        self.set_node_attributes([node], new_node_attrs)

        incident_edges = list(self.graph.in_edges(node)) + list(
            self.graph.out_edges(node)
        )
        for edge in incident_edges:
            new_edge_attrs = self._compute_edge_attrs(edge)
            new_edge_attrs = {attr: [val] for attr, val in new_edge_attrs.items()}
            self.set_edge_attributes([edge], new_edge_attrs)

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
