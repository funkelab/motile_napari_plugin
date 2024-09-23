from typing import Any

import numpy as np
from motile_toolbox.candidate_graph import NodeAttr
from motile_toolbox.candidate_graph.utils import get_node_id
from skimage import measure

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
    ) -> None:
        """Calls the _add_nodes function to add nodes. Calls the refresh signal when finished.

        Args:
            nodes (np.ndarray[int]):an array of node ids
            attributes (dict[str, np.ndarray]): dictionary containing at least time and position attributes
            segmentations (Any, optional): A segmentation for each node (not
                currently implemented). Defaults to None.
        """

        self._add_nodes(nodes, attributes)
        self.tracks.refresh.emit(nodes[0] if nodes else None)

    def _add_nodes(self, nodes: np.ndarray[int], attributes: dict[str, np.ndarray]):
        """Add nodes to the graph. Includes all attributes and the segmentation.

        Args:
            nodes (np.ndarray[int]):an array of node ids
            attributes (dict[str, np.ndarray]): dictionary containing at least time and position attributes
            segmentations (Any, optional): A segmentation for each node (not
                currently implemented). Defaults to None.
        """

        for idx, node in enumerate(nodes):
            attrs = {attr: val[idx] for attr, val in attributes.items()}
            self.tracks.graph.add_node(node, **attrs)
            track_id = attrs[NodeAttr.TRACK_ID.value]
            if track_id in self.tracks.node_id_to_track_id.values():
                # this track_id already exists, find the nearest predecessor and nearest successor to create new edge
                candidates = [
                    n
                    for n in self.tracks.node_id_to_track_id
                    if self.tracks.node_id_to_track_id[n] == track_id
                ]

                # Sort candidates by their 'time' attribute
                candidates.sort(
                    key=lambda n: self.tracks.graph.nodes[n][NodeAttr.TIME.value]
                )
                closest_predecessor = None
                closest_successor = None
                current_time = self.tracks.graph.nodes[node].get(NodeAttr.TIME.value)

                for candidate in candidates:
                    candidate_time = self.tracks.graph.nodes[candidate][
                        NodeAttr.TIME.value
                    ]
                    if candidate_time < current_time:
                        closest_predecessor = candidate
                    elif candidate_time > current_time and closest_successor is None:
                        closest_successor = candidate
                        break

                if (
                    closest_predecessor is not None
                    and closest_successor is not None
                    and self.tracks.graph.has_edge(
                        closest_predecessor, closest_successor
                    )
                ):
                    self.tracks.graph.remove_edge(
                        closest_predecessor, closest_successor
                    )  # first delete existing skip edge before connecting again

                if closest_predecessor is not None and not self.tracks.graph.has_edge(
                    closest_predecessor, node
                ):
                    attrs = {}
                    self.tracks.graph.add_edge(closest_predecessor, node, **attrs)
                if closest_successor is not None and not self.tracks.graph.has_edge(
                    node, closest_successor
                ):
                    attrs = {}
                    self.tracks.graph.add_edge(node, closest_successor, **attrs)

            self.tracks.node_id_to_track_id[node] = track_id

    def delete_nodes(self, nodes: np.ndarray[Any]) -> None:
        """Calls the _delete_nodes function and then emits the refresh signal

        Args:
            nodes (np.ndarray): array of node_ids to be deleted
        """

        self._delete_nodes(nodes)
        self.tracks.refresh.emit()

    def _delete_nodes(self, nodes: np.ndarray[Any]):
        """Delete the nodes provided by the array from the graph but maintain successor track_ids. Reconnect to the
        nearest predecessor and/or nearest successor, if any.

        Args:
            nodes (np.ndarray): array of node_ids to be deleted
        """

        for node in nodes:
            # first delete the segmentation if there is one.
            if self.tracks.segmentation is not None:  # and delete_seg is True
                self._delete_segmentation(node)

            preds = list(self.tracks.graph.predecessors(node))
            succs = list(self.tracks.graph.successors(node))
            if len(preds) == 0:  # do nothing - track ids are fine
                continue
            pred = preds[0]  # assume can't have two preds, no merging (yet)
            siblings = list(self.tracks.graph.successors(pred))
            if len(siblings) == 2:
                # need to relabel the track id of the sibling to match the pred because
                # you are implicitly deleting a division
                siblings.remove(node)
                new_track_id = self.tracks.get_track_id(pred)
                self._assign_new_track_id(siblings[0], new_track_id)
            elif len(succs) == 1 and len(preds) == 1:
                # make new (skip) edge between predecessor and successor
                attrs = {}
                self.tracks.graph.add_edge(preds[0], succs[0], **attrs)
            # if succs == 2, do nothing = the children already have different track ids

            del self.tracks.node_id_to_track_id[node]

        # remove nodes from the graph
        self.tracks.graph.remove_nodes_from(nodes)

    def _delete_segmentation(self, node: Any) -> None:
        """Delete the node from the segmentation (set it to 0)

        Args:
            node (Any): The node to be deleted.

        """

        time = self.tracks.get_time(node)
        track_id = self.tracks.get_track_id(node)
        self.tracks.update_segmentation(time, track_id, 0)

    def _assign_new_track_id(self, start_node: Any, new_track_id: int):
        """Helper function to assign a new track id to the track starting with start_node.
        Will also update the self.tracks.segmentation array and seg_id on the
        self.tracks.graph if a segmentation exists.

        Args:
            start_node (Any): The node ID of the first node in the track. All successors
                with the same track id as this node will be updated.
            new_track_id (int): The new track id to assign.
        """

        old_track_id = self.tracks.get_track_id(start_node)
        curr_node = start_node
        while self.tracks.get_track_id(curr_node) == old_track_id:
            # update the track id
            self.tracks.graph.nodes[curr_node][NodeAttr.TRACK_ID.value] = new_track_id
            self.tracks.node_id_to_track_id[curr_node] = new_track_id
            if self.tracks.segmentation is not None:
                time = self.tracks.get_time(curr_node)
                # update the segmentation to match the new track id
                self.tracks.update_segmentation(time, old_track_id, new_track_id)
                # update the graph seg_id attr to match the new seg id
                self.tracks.graph.nodes[curr_node][NodeAttr.SEG_ID.value] = new_track_id
            # getting the next node (picks one if there are two)
            successors = list(self.tracks.graph.successors(curr_node))
            if len(successors) == 0:
                break
            curr_node = successors[0]

    def update_track_ids(self, edges_changed: list[Any]) -> None:
        """Reassign the track_ids and relabel the segmentation and update seg_id attr
        if present. Assumes that the edges being passed have already been removed or
        added.

        Args:
            edges_changed (list[Any]): A list of edges that have been removed or added
        """
        for edge in edges_changed:
            if self.tracks.graph.has_edge(*edge):
                # edge was added
                out_degree = self.tracks.graph.out_degree(edge[0])
                if out_degree == 1:  # joined two segments
                    # assign the track id of the source node to the target and all out
                    # edges until end of track
                    new_track_id = self.tracks.get_track_id(edge[0])
                    self._assign_new_track_id(edge[1], new_track_id)
                elif out_degree == 2:  # created a division
                    # assign a new track id to both child tracks
                    for successor in self.tracks.graph.successors(edge[0]):
                        new_track_id = self.tracks.get_next_track_id()
                        self._assign_new_track_id(successor, new_track_id)
                else:
                    raise RuntimeError(
                        f"Expected degree of 1 or 2 after adding edge, got {out_degree}"
                    )
            else:
                # edge was deleted
                out_degree = self.tracks.graph.out_degree(edge[0])
                if out_degree == 0:  # removed a normal (non division) edge
                    new_track_id = self.tracks.get_next_track_id()
                    self._assign_new_track_id(edge[1], new_track_id)
                elif out_degree == 1:  # removed a division edge
                    sibling = next(iter(self.tracks.graph.successors(edge[0])))
                    new_track_id = self.tracks.get_track_id(edge[0])
                    self._assign_new_track_id(sibling, new_track_id)
                else:
                    raise RuntimeError(
                        f"Expected degree of 0 or 1 after removing edge, got {out_degree}"
                    )

    def update_nodes(self, nodes: np.ndarray[Any], attributes: dict[str, np.ndarray]):
        """Calls the _update_nodes function to update the node attributtes in given array.
        Then calls the refresh signal.

        Args:
        nodes (np.ndarray[int]):an array of node ids
        attributes (dict[str, np.ndarray]): dictionary containing the attributes to be updated

        """

        self._update_nodes(nodes, attributes)
        self.tracks.refresh.emit()

    def _update_nodes(self, nodes: np.ndarray[Any], attributes: dict[str, np.ndarray]):
        """Update the attributes for the nodes in the given array.

        Args:
        nodes (np.ndarray[int]):an array of node ids
        attributes (dict[str, np.ndarray]): dictionary containing the attributes to be updated

        """

        for node in nodes:
            if node in self.tracks.graph:
                for key, value in attributes.items():
                    if key in self.tracks.graph.nodes[node]:
                        self.tracks.graph.nodes[node][key] = value[
                            np.where(nodes == node)[0][0]
                        ]
                    else:
                        print(
                            f"Attribute '{key}' does not exist for node {node}. Adding it."
                        )
                        self.tracks.graph.nodes[node][key] = value[
                            np.where(nodes == node)[0][0]
                        ]
            else:
                print(f"Node {node} not found in the graph.")

    def add_edges(self, edges: np.ndarray[int], attributes: dict[str, np.ndarray]):
        """Add edges and attributes to the graph. Also update the track ids and
        corresponding segmentations if applicable

        Args:
            edges (np.array[int]): An Nx2 array of N edges, each with source and target
                node ids
            attributes (dict[str, np.ndarray]): dictionary mapping attribute names to
                an array of values, where the index in the array matches the edge index
        """

        self._add_edges(edges, attributes)
        self.tracks.refresh.emit()

    def _add_edges(self, edges: np.ndarray[int], attributes: dict[str, np.ndarray]):
        """Add edges and attributes to the graph. Also update the track ids and
        corresponding segmentations if applicable

        Args:
            edges (np.array[int]): An Nx2 array of N edges, each with source and target
                node ids
            attributes (dict[str, np.ndarray]): dictionary mapping attribute names to
                an array of values, where the index in the array matches the edge index
        """

        for idx, edge in enumerate(edges):
            if self.is_valid(edge):
                attrs = {attr: val[idx] for attr, val in attributes.items()}
                self.tracks.graph.add_edge(edge[0], edge[1], **attrs)

        self.update_track_ids(edges)

    def is_valid(self, edge):
        """Check if this edge is valid.
        criteria:
            - not horizontal
            - not existing yet
            - source node does not already have an upstream target node of the same track_id

        Args:
            edge (np.ndarray[(int, int)]: edge to be validated
        Returns:
            True if the edge is valid, false if invalid"""

        # TODO implement this function
        return True

    def delete_edges(self, edges: np.ndarray):
        """Delete edges from the graph.

        Args:
            edges (np.ndarray): _description_
        """
        self.tracks.graph.remove_edges_from(edges)
        self.update_track_ids(edges)
        self.tracks.refresh.emit()

    def update_edges(self, edges: np.ndarray[int], attributes: np.ndarray):
        pass

    def update_segmentations(
        self,
        time_points: list[int],
        current_timepoint: int,
        changed_track_ids: list[int],
    ):
        """Handle a change in the segmentation mask, checking for node addition, deletion, and attribute updates.
        Args:
            time_points (list[int]): list of the affected time points
            current_timepoint (int): the current time point in the viewer, used to set the selected node.
            changed_track_ids (list[int]): list of the affected track_ids.

        """

        node_to_select = None
        for t in time_points:
            deleted = []
            updated_nodes = []
            updated_node_attrs = {NodeAttr.AREA.value: [], NodeAttr.POS.value: []}
            new_nodes = []
            new_node_attrs = {
                NodeAttr.TIME.value: [],
                NodeAttr.SEG_ID.value: [],
                NodeAttr.TRACK_ID.value: [],
                NodeAttr.AREA.value: [],
                NodeAttr.POS.value: [],
            }
            nodes = [
                (n, attr)
                for n, attr in self.tracks.graph.nodes(data=True)
                if attr.get(NodeAttr.TIME.value) == t
            ]
            for track_id in changed_track_ids:
                array = self.tracks.segmentation[t, 0] == track_id
                area = np.sum(array)
                node_id = next(
                    (
                        n
                        for n, attr in nodes
                        if attr.get(NodeAttr.TIME.value) == t
                        and attr.get(NodeAttr.TRACK_ID.value) == track_id
                    ),
                    None,
                )
                if node_id is not None:
                    if area == 0:
                        # this node was removed
                        deleted.append(node_id)
                    else:
                        # this node was updated
                        updated_node_attrs[NodeAttr.POS.value].append(
                            measure.centroid(array, spacing=self.tracks.scale)
                        )
                        updated_node_attrs[NodeAttr.AREA.value].append(
                            area * np.prod(self.tracks.scale)
                        )
                        updated_nodes.append(node_id)
                else:
                    # this node does not yet exist in the graph, adding it.
                    node_id = get_node_id(t, track_id)
                    new_nodes.append(node_id)
                    new_node_attrs[NodeAttr.TIME.value].append(t)
                    new_node_attrs[NodeAttr.POS.value].append(
                        measure.centroid(array, spacing=self.tracks.scale)
                    )
                    new_node_attrs[NodeAttr.AREA.value].append(
                        area * np.prod(self.tracks.scale)
                    )
                    new_node_attrs[NodeAttr.TRACK_ID.value].append(track_id)
                    new_node_attrs[NodeAttr.SEG_ID.value].append(track_id)

            # delete nodes from the graph
            if len(deleted) > 0:
                self._delete_nodes(np.array(deleted))

            # update node attributes in the graph
            if len(updated_nodes) > 0:
                for key in updated_node_attrs:
                    updated_node_attrs[key] = np.array(updated_node_attrs[key])
                self._update_nodes(np.array(updated_nodes), updated_node_attrs)

            # add new nodes (and edges) to the graph
            if len(new_nodes) > 0:
                for key in new_node_attrs:
                    new_node_attrs[key] = np.array(new_node_attrs[key])
                self._add_nodes(np.array(new_nodes), new_node_attrs)

            # if this is the time point where the user added a node, select the new node
            if t == current_timepoint:
                node_to_select = new_nodes[0] if new_nodes else None

        self.tracks.refresh.emit(node_to_select)

    def add_node_attribute(self, name: str, values: any):
        pass

    def add_edge_attribute(self, name: str, values: any):
        pass

    def remove_node_attribute(self, name: str):
        pass
