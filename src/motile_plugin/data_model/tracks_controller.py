from typing import Any

import numpy as np
from motile_toolbox.candidate_graph import NodeAttr

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

    def delete_nodes(self, nodes: np.ndarray[Any]) -> None:
        """_summary_

        Args:
            nodes (np.ndarray): _description_
        """
        for node in nodes:
            # first delete the segmentation if there is one.
            if self.tracks.segmentation is not None:
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
            if len(succs) == 1:
                new_track_id = self.tracks.get_next_track_id()
                self._assign_new_track_id(succs[0], new_track_id)

            # if succs == 2, do nothing = the children already have different track ids
        # remove nodes from the graph
        self.tracks.graph.remove_nodes_from(nodes)
        self.tracks.refresh.emit()

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
        pass

    def add_edges(self, edges: np.ndarray[int], attributes: dict[str, np.ndarray]):
        """Add edges and attributes to the graph. Also update the track ids and
        corresponding segmentations if applicable

        Args:
            edges (np.array[int]): An Nx2 array of N edges, each with source and target
                node ids
            attributes (dict[str, np.ndarray]): dictionary mapping attribute names to
                an array of values, where the index in the array matches the edge index
        """

        for idx, edge in enumerate(edges):
            print(edge)
            attrs = {attr: val[idx] for attr, val in attributes.items()}
            self.tracks.graph.add_edge(edge[0], edge[1], **attrs)

        self.update_track_ids(edges)
        self.tracks.refresh.emit()

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

    def update_segmentations(self, nodes: np.ndarray[int], updated_values: Any):
        pass

    def add_node_attribute(self, name: str, values: any):
        pass

    def add_edge_attribute(self, name: str, values: any):
        pass

    def remove_node_attribute(self, name: str):
        pass
