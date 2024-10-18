from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    TypeAlias,
)

import networkx as nx
import numpy as np
from motile_toolbox.candidate_graph import EdgeAttr, NodeAttr
from motile_toolbox.candidate_graph.iou import _compute_ious
from psygnal import Signal
from skimage import measure

if TYPE_CHECKING:
    from pathlib import Path

AttrValue: TypeAlias = Any
Node: TypeAlias = Any
Edge: TypeAlias = tuple[Node, Node]
AttrValues: TypeAlias = Sequence[AttrValue]
Attrs: TypeAlias = Mapping[str, AttrValues]
SegMask: TypeAlias = tuple[np.ndarray, ...]


class Tracks:
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

    For bulk operations on attributes, a KeyError will be raised if a node or edge
    in the input set is not in the graph. All operations before the error node will
    be performed, and those after will not.

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
        ndim: int | None = None,
    ):
        self.graph = graph
        self.segmentation = segmentation
        self.time_attr = time_attr
        self.pos_attr = pos_attr
        self.scale = scale
        self.ndim = self._compute_ndim(segmentation, scale, ndim)
        self.seg_time_to_node = self._create_seg_time_to_node()

    def get_positions(
        self, nodes: Iterable[Node], incl_time: bool = False
    ) -> np.ndarray:
        """Get the positions of nodes in the graph. Optionally include the
        time frame as the first dimension. Raises an error if any of the nodes
        are not in the graph.

        Args:
            node (Iterable[Node]): The node ids in the graph to get the positions of
            incl_time (bool, optional): If true, include the time as the
                first element of each position array. Defaults to False.

        Returns:
            np.ndarray: A N x ndim numpy array holding the positions, where N is the
                number of nodes passed in
        """
        if isinstance(self.pos_attr, tuple | list):
            positions = np.stack(
                [
                    self._get_nodes_attr(nodes, dim, required=True)
                    for dim in self.pos_attr
                ],
                axis=1,
            )
        else:
            positions = np.array(
                self._get_nodes_attr(nodes, self.pos_attr, required=True)
            )

        if incl_time:
            times = np.array(self._get_nodes_attr(nodes, self.time_attr, required=True))
            positions = np.c_[times, positions]

        return positions

    def get_position(self, node: Node, incl_time=False) -> list:
        return self.get_positions([node], incl_time=incl_time)[0].tolist()

    def set_positions(
        self,
        nodes: Iterable[Node],
        positions: np.ndarray | Iterable[Edge],
        incl_time: bool = False,
    ):
        """Set the location of a node in the graph. Optionally include the
        time frame as the first dimension. Raises an error if the node
        is not in the graph.

        Args:
            node (Any): The node id in the graph to set the location of.
            location (np.ndarray): The location to set. If incl_time is true, time
                is the first element.
            incl_time (bool, optional): If true, include the time as the
                first element of the location array. Defaults to False.
        """
        if not isinstance(positions, np.ndarray):
            positions = np.array(positions)
        if incl_time:
            self.set_times(nodes, positions[:, 0].tolist())
            positions = positions[:, 1:]

        if isinstance(self.pos_attr, tuple | list):
            for idx, attr in enumerate(self.pos_attr):
                self._set_nodes_attr(nodes, attr, positions[:, idx].tolist())
        else:
            self._set_nodes_attr(nodes, self.pos_attr, positions.tolist())

    def set_position(self, node: Node, position: list, incl_time=False):
        self.set_positions(
            [node], np.expand_dims(np.array(position), axis=0), incl_time=incl_time
        )

    def get_times(self, nodes: Iterable[Node]) -> Sequence[int]:
        return self._get_nodes_attr(nodes, self.time_attr, required=True)

    def get_time(self, node: Node) -> int:
        """Get the time frame of a given node. Raises an error if the node
        is not in the graph.

        Args:
            node (Any): The node id to get the time frame for

        Returns:
            int: The time frame that the node is in
        """
        return int(self.get_times([node])[0])

    def set_times(self, nodes: Iterable[Node], times: Iterable[int]):
        self._remove_from_seg_time_to_node(nodes)
        self._set_nodes_attr(nodes, self.time_attr, times)
        self._add_to_seg_time_to_node(nodes)

    def set_time(self, node: Any, time: int):
        """Set the time frame of a given node. Raises an error if the node
        is not in the graph.

        Args:
            node (Any): The node id to set the time frame for
            time (int): The time to set

        """
        self.set_times([node], [time])

    def get_seg_ids(
        self, nodes: Iterable[Node], required=False
    ) -> Sequence[int | None]:
        return self._get_nodes_attr(nodes, NodeAttr.SEG_ID.value, required=required)

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
        return self.get_seg_ids([node])[0]

    def set_seg_ids(self, nodes: Iterable[Node], seg_ids: Iterable[int]):
        """Get the segmentation id of a given node. Raises a KeyError if the node
        is not in the graph.

        Args:
            node (Any): The node id to set the seg id of
            seg_id (int): The segmentation id to set for the node
        """
        self._remove_from_seg_time_to_node(nodes)
        self._set_nodes_attr(nodes, NodeAttr.SEG_ID.value, seg_ids)
        self._add_to_seg_time_to_node(nodes)

    def set_seg_id(self, node: Node, seg_id: int):
        self.set_seg_ids([node], [seg_id])

    def add_nodes(
        self,
        nodes: Iterable[Node],
        times: Iterable[int],
        positions: np.ndarray | None = None,
        seg_ids: Iterable[int] | None = None,
        attrs: Attrs | None = None,
    ):
        if attrs is None:
            attrs = {}
        self.graph.add_nodes_from(nodes)
        self.set_times(nodes, times)
        final_pos: np.ndarray
        if seg_ids is not None and self.segmentation is not None:
            self.set_seg_ids(nodes, seg_ids)
            computed_attrs = self._compute_node_attrs(seg_ids, times)
            if positions is None:
                final_pos = np.array(computed_attrs[NodeAttr.POS.value])
            else:
                final_pos = positions
            areas = computed_attrs[NodeAttr.AREA.value]
            attrs[NodeAttr.AREA.value] = areas
        elif positions is None:
            raise ValueError("Must provide positions or segmentation and ids")
        else:
            final_pos = positions

        self.set_positions(nodes, final_pos)
        for attr, values in attrs.items():
            self._set_nodes_attr(nodes, attr, values)

        self._add_to_seg_time_to_node(nodes)

    def add_node(
        self,
        node: Node,
        time: int,
        position: Sequence | None = None,
        seg_id: int | None = None,
        attrs: Attrs | None = None,
    ):
        """Add a node to the graph. Will update the internal mappings and generate the
        segmentation-controlled attributes if there is a segmentation present.
        The segmentation should have been previously updated, otherwise the
        attributes will not update properly.

        Args:
            node (Node): The node id to add
            time (int): the time frame of the node to add
            position (Seqeunce | None): The spatial position of the node (excluding time).
                Can be None if it should be automatically detected from the segmentation.
                Either seg_id or position must be provided. Defaults to None.
            seg_id (int | None): The segmentation id of the node, used to match the node
                to the segmentation at the given time, or None if the node does not have
                a matching segmentation. Either seg_id or position must be provided.
                Defaults to None.
        """
        pos = np.expand_dims(position, axis=0) if position is not None else None
        seg_ids = [seg_id] if seg_id is not None else None
        attributes: dict[str, Sequence[Any]] | None = (
            {key: [val] for key, val in attrs.items()} if attrs is not None else None
        )
        self.add_nodes([node], [time], positions=pos, seg_ids=seg_ids, attrs=attributes)

    def remove_nodes(self, nodes: Iterable[Node]):
        self._remove_from_seg_time_to_node(nodes)
        self.graph.remove_nodes_from(nodes)

    def remove_node(self, node: Node):
        """Remove the node from the graph and update the internal mappings.
        Does not update the segmentation if present.

        Args:
            node (Node): The node to remove from the graph
        """

        self.remove_nodes([node])

    def add_edges(self, edges: Iterable[Edge]):
        attrs: dict[str, Sequence[Any]] = {}
        attrs.update(self._compute_edge_attrs(edges))
        for idx, edge in enumerate(edges):
            for node in edge:
                if not self.graph.has_node(node):
                    raise KeyError(
                        f"Cannot add edge {edge}: endpoint {node} not in graph yet"
                    )
            self.graph.add_edge(
                edge[0], edge[1], **{key: vals[idx] for key, vals in attrs.items()}
            )

    def add_edge(self, edge: Edge):
        self.add_edges([edge])

    def remove_edges(self, edges: Iterable[Edge]):
        for edge in edges:
            self.remove_edge(edge)

    def remove_edge(self, edge: Edge):
        if self.graph.has_edge(*edge):
            self.graph.remove_edge(*edge)
        else:
            raise KeyError(f"Edge {edge} not in the graph, and cannot be removed")

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

    def get_areas(self, nodes: Iterable[Node]) -> Sequence[int | None]:
        """Get the area/volume of a given node. Raises a KeyError if the node
        is not in the graph. Returns None if the given node does not have an Area
        attribute.

        Args:
            node (Node): The node id to get the area/volume for

        Returns:
            int: The area/volume of the node
        """
        return self._get_nodes_attr(nodes, NodeAttr.AREA.value)

    def get_area(self, node: Node) -> int | None:
        """Get the area/volume of a given node. Raises a KeyError if the node
        is not in the graph. Returns None if the given node does not have an Area
        attribute.

        Args:
            node (Node): The node id to get the area/volume for

        Returns:
            int: The area/volume of the node
        """
        return self.get_areas([node])[0]

    def get_ious(self, edges: Iterable[Edge]):
        return self._get_edges_attr(edges, EdgeAttr.IOU.value)

    def get_iou(self, edge: Edge):
        return self._get_edge_attr(edge, EdgeAttr.IOU.value)

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
            seg_id = self.get_seg_id(node)
            if seg_id is None:
                pix_list.append((np.array([], dtype=np.uint64),) * self.ndim)
            else:
                time = self.get_time(node)
                loc_pixels = np.nonzero(self.segmentation[time][0] == seg_id)
                time_array = np.ones_like(loc_pixels[0]) * time
                hypo_array = np.zeros_like(loc_pixels[0])
                pix_list.append((time_array, hypo_array, *loc_pixels))
        return pix_list

    def set_pixels(
        self, pixels: Iterable[tuple[np.ndarray, ...]], values: Iterable[int | None]
    ):
        """Set the given pixels in the segmentation to the given value.

        Args:
            pixels (Iterable[tuple[np.ndarray]]): The pixels that should be set,
                formatted like the output of np.nonzero (each element of the tuple
                represents one dimension, containing an array of indices in that dimension).
                Can be used to directly index the segmentation.
            value (Iterable[int | None]): The value to set each pixel to
        """
        if self.segmentation is None:
            raise ValueError("Cannot set pixels when segmentation is None")
        for pix, val in zip(pixels, values, strict=False):
            if val is None:
                raise ValueError("Cannot set pixels to None value")
            if len(pix) == self.ndim:
                # add dummy hypothesis dimension for now
                pix = (pix[0], np.zeros_like(pix[0]), *pix[1:])
            self.segmentation[pix] = val

    def update_segmentations(
        self, nodes: Iterable[Node], pixels: Iterable[SegMask], added: bool = True
    ) -> None:
        """Updates the segmentation of the given nodes. Also updates the
        auto-computed attributes of the nodes and incident edges.
        """
        times = self.get_times(nodes)
        seg_ids = self.get_seg_ids(nodes, required=True)
        values = (
            seg_ids
            if added
            else [
                0,
            ]
            * len(seg_ids)
        )
        self.set_pixels(pixels, values)
        computed_attrs = self._compute_node_attrs(seg_ids, times)
        positions = np.array(computed_attrs[NodeAttr.POS.value])
        self.set_positions(nodes, positions)
        self._set_nodes_attr(
            nodes, NodeAttr.AREA.value, computed_attrs[NodeAttr.AREA.value]
        )

        incident_edges = list(self.graph.in_edges(nodes)) + list(
            self.graph.out_edges(nodes)
        )
        for edge in incident_edges:
            new_edge_attrs = self._compute_edge_attrs([edge])
            self._set_edge_attributes([edge], new_edge_attrs)

    def _set_node_attributes(self, nodes: Iterable[Node], attributes: Attrs):
        """Update the attributes for given nodes"""

        for idx, node in enumerate(nodes):
            if node in self.graph:
                for key, values in attributes.items():
                    self.graph.nodes[node][key] = values[idx]
            else:
                print(f"Node {node} not found in the graph.")

    def _set_edge_attributes(self, edges: Iterable[Edge], attributes: Attrs) -> None:
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
            "time_attr": self.time_attr
            if not isinstance(self.time_attr, np.ndarray)
            else self.time_attr.tolist(),
            "pos_attr": self.pos_attr
            if not isinstance(self.pos_attr, np.ndarray)
            else self.pos_attr.tolist(),
            "scale": self.scale
            if not isinstance(self.scale, np.ndarray)
            else self.scale.tolist(),
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

    def _compute_ndim(
        self,
        seg: np.ndarray | None,
        scale: list[float] | None,
        provided_ndim: int | None,
    ):
        seg_ndim = seg.ndim - 1 if seg is not None else None  # remove hypothesis dim
        scale_ndim = len(scale) if scale is not None else None
        ndims = [seg_ndim, scale_ndim, provided_ndim]
        ndims = [d for d in ndims if d is not None]
        if len(ndims) == 0:
            raise ValueError(
                "Cannot compute dimensions from segmentation or scale: please provide ndim argument"
            )
        ndim = ndims[0]
        if not all(d == ndim for d in ndims):
            raise ValueError(
                f"Dimensions from segmentation {seg_ndim}, scale {scale_ndim}, and ndim {provided_ndim} must match"
            )
        return ndim

    def _create_seg_time_to_node(self) -> dict[int, dict[int, Node]]:
        """Create a dictionary mapping seg_id -> dict(time_point -> node_id)"""
        seg_time_to_node: dict[int, dict[int, Node]] = {}
        if self.segmentation is None:
            return seg_time_to_node

        for node in self.graph.nodes():
            seg_id = self.get_seg_id(node)
            if seg_id is None:
                continue
            if seg_id not in seg_time_to_node:
                seg_time_to_node[seg_id] = {}
            time = self.get_time(node)
            seg_time_to_node[seg_id][time] = node
        return seg_time_to_node

    def _set_node_attr(self, node: Node, attr: NodeAttr, value: Any):
        if isinstance(value, np.ndarray):
            value = list(value)
        self.graph.nodes[node][attr] = value

    def _set_nodes_attr(self, nodes: Iterable[Node], attr: str, values: Iterable[Any]):
        for node, value in zip(nodes, values, strict=False):
            if isinstance(value, np.ndarray):
                value = list(value)
            self.graph.nodes[node][attr] = value

    def _get_node_attr(self, node: Node, attr: str, required: bool = False):
        if required:
            return self.graph.nodes[node][attr]
        else:
            return self.graph.nodes[node].get(attr, None)

    def _get_nodes_attr(self, nodes: Iterable[Node], attr: str, required: bool = False):
        return [self._get_node_attr(node, attr, required=required) for node in nodes]

    def _set_edge_attr(self, edge: Edge, attr: str, value: Any):
        self.graph.edge[edge][attr] = value

    def _set_edges_attr(self, edges: Iterable[Edge], attr: str, values: Iterable[Any]):
        for edge, value in zip(edges, values, strict=False):
            self.graph.edges[edge][attr] = value

    def _get_edge_attr(self, edge: Edge, attr: str, required: bool = False):
        if required:
            return self.graph.edges[edge][attr]
        else:
            return self.graph.edges[edge].get(attr, None)

    def _get_edges_attr(self, edges: Iterable[Edge], attr: str, required: bool = False):
        return [self._get_edge_attr(edge, attr, required=required) for edge in edges]

    def _remove_from_seg_time_to_node(self, nodes: Iterable[Node]):
        for node in nodes:
            seg_id = self.get_seg_id(node)
            time = self._get_node_attr(node, self.time_attr, required=False)
            if (
                seg_id is not None
                and time is not None
                and seg_id in self.seg_time_to_node
                and time in self.seg_time_to_node[seg_id]
            ):
                del self.seg_time_to_node[seg_id][time]

    def _add_to_seg_time_to_node(self, nodes: Iterable[Node]):
        for node in nodes:
            seg_id = self.get_seg_id(node)
            if seg_id is None:
                continue
            time = self.get_time(node)
            if seg_id not in self.seg_time_to_node:
                self.seg_time_to_node[seg_id] = {}
            self.seg_time_to_node[seg_id][time] = node

    def _compute_node_attrs(
        self, seg_ids: Iterable[int | None], times: Iterable[int]
    ) -> Attrs:
        """Get the segmentation controlled node attributes (area and position)
        from the segmentation with label seg_id in the given time point.

        Args:
            seg_id (int): The label id to query the current segmentation for
            time (int): The time frame of the current segmentation to query

        Returns:
            dict[str, int]: A dictionary containing the attributes that could be
                determined from the segmentation. It will be empty if self.segmentation
                is None. If self.segmentation exists but seg_id is not present in time,
                area will be 0 and position will be None. If self.segmentation
                exists and seg_id is present in time, area and position will be included.
        """
        if self.segmentation is None:
            return {}

        attrs: dict[str, list[Any]] = {
            NodeAttr.POS.value: [],
            NodeAttr.AREA.value: [],
        }
        for seg_id, time in zip(seg_ids, times, strict=False):
            if seg_id is None:
                area = None
                pos = None
            else:
                seg = self.segmentation[time][0] == seg_id
                area = np.sum(seg)
                if self.scale is not None:
                    area *= np.prod(self.scale)
                # only include the position if the segmentation was actually there
                pos = (
                    measure.centroid(seg, spacing=self.scale)
                    if area > 0
                    else np.array(
                        [
                            None,
                        ]
                        * (self.ndim - 1)
                    )
                )
            attrs[NodeAttr.AREA.value].append(area)
            attrs[NodeAttr.POS.value].append(pos)
        attrs[NodeAttr.POS.value] = np.array(attrs[NodeAttr.POS.value])
        return attrs

    def _compute_edge_attrs(self, edges: Iterable[Edge]) -> Attrs:
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
        if self.segmentation is None:
            return {}

        attrs: dict[str, list[Any]] = {EdgeAttr.IOU.value: []}
        for edge in edges:
            source, target = edge
            source_seg = self.get_seg_id(source)
            target_seg = self.get_seg_id(target)
            if source_seg is None or target_seg is None:
                iou = 0
            else:
                source_time = self.get_time(source)
                target_time = self.get_time(target)

                source_arr = self.segmentation[source_time][0] == source_seg
                target_arr = self.segmentation[target_time][0] == target_seg

                iou_list = _compute_ious(
                    source_arr, target_arr
                )  # list of (id1, id2, iou)
                iou = 0 if len(iou_list) == 0 else iou_list[0][2]

            attrs[EdgeAttr.IOU.value].append(iou)
        return attrs
