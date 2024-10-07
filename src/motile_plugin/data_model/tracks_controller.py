from typing import Any

import numpy as np
from motile_toolbox.candidate_graph import NodeAttr
from motile_toolbox.candidate_graph.utils import get_node_id
from napari.utils.notifications import show_warning
from qtpy.QtWidgets import QMessageBox
from skimage import measure

from .action_history import ActionHistory
from .actions import (
    ActionGroup,
    AddEdges,
    AddNodes,
    DeleteEdges,
    DeleteNodes,
    TracksAction,
    UpdateNodes,
    UpdateTrackID,
)
from .tracks import Attributes, Node, SegMask, Tracks


class TracksController:
    """A set of high level functions to change the data model.
    All changes to the data should go through this API.
    """

    def __init__(self, tracks: Tracks):
        self.tracks = tracks
        self.action_history = ActionHistory()

    def add_nodes(
        self,
        nodes: list[Node],
        attributes: Attributes,
        pixels: SegMask,
    ) -> None:
        """Calls the _add_nodes function to add nodes. Calls the refresh signal when finished.

        Args:
            nodes (np.ndarray[int]):an array of node ids
            attributes (dict[str, np.ndarray]): dictionary containing at least time and position attributes
        """

        action = self._add_nodes(nodes, attributes, pixels)
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit(nodes[0] if nodes else None)

    def _add_nodes(
        self, nodes: list[Node], attributes: Attributes, pixels: SegMask
    ) -> TracksAction:
        """Add nodes to the graph. Includes all attributes and the segmentation.

        Args:
            nodes (list[Node]): a list of node ids
            attributes (Attributes): dictionary containing at least time and position attributes
        """
        actions = [
            AddNodes(
                tracks=self.tracks,
                nodes=nodes,
                attributes=attributes,
                pixels=pixels,
            )
        ]
        for idx, node in enumerate(nodes):
            attrs = {attr: val[idx] for attr, val in attributes.items()}
            current_time = attrs[NodeAttr.TIME.value]
            track_id = attrs[NodeAttr.TRACK_ID.value]
            if track_id in self.tracks.track_time_to_node:
                # this track_id already exists, find the nearest predecessor and nearest successor to create new edge
                candidates = self.tracks.track_time_to_node[track_id].values()

                # Sort candidates by their 'time' attribute
                candidates.sort(
                    key=lambda n: self.tracks.graph.nodes[n][NodeAttr.TIME.value]
                )
                closest_predecessor = None
                closest_successor = None

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
                    actions.append(
                        DeleteEdges(
                            self.tracks, [(closest_predecessor, closest_successor)]
                        )
                    )

                if closest_predecessor is not None and not self.tracks.graph.has_edge(
                    closest_predecessor, node
                ):
                    actions.append(
                        AddEdges(self.tracks, [(closest_predecessor, node)], {})
                    )
                if closest_successor is not None and not self.tracks.graph.has_edge(
                    node, closest_successor
                ):
                    actions.append(
                        AddEdges(self.tracks, [(node, closest_successor)], {})
                    )

        return ActionGroup(self.tracks, actions)

    def delete_nodes(self, nodes: np.ndarray[Any]) -> None:
        """Calls the _delete_nodes function and then emits the refresh signal

        Args:
            nodes (np.ndarray): array of node_ids to be deleted
        """

        action = self._delete_nodes(nodes)
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit()

    def _delete_nodes(self, nodes: np.ndarray[Any]) -> TracksAction:
        """Delete the nodes provided by the array from the graph but maintain successor track_ids. Reconnect to the
        nearest predecessor and/or nearest successor, if any.

        Args:
            nodes (np.ndarray): array of node_ids to be deleted
        """
        actions = []
        for node in nodes:
            preds = list(self.tracks.graph.predecessors(node))
            succs = list(self.tracks.graph.successors(node))
            if len(preds) == 0:  # do nothing - track ids are fine
                continue
            pred = preds[0]  # assume can't have two preds, no merging (yet)

            # remove incident edges in an undo-able fashion
            actions.append(DeleteEdges(self.tracks, [(pred, node)]))
            for succ in succs:
                actions.append(DeleteEdges(self.tracks, [(node, succ)]))

            # determine if we need to relabel any tracks or add skip edges
            siblings = list(self.tracks.graph.successors(pred))
            if len(siblings) == 2:
                # need to relabel the track id of the sibling to match the pred because
                # you are implicitly deleting a division
                siblings.remove(node)
                new_track_id = self.tracks.get_track_id(pred)
                actions.append(UpdateTrackID(self.tracks, siblings[0], new_track_id))
            elif len(succs) == 1 and len(preds) == 1:
                # make new (skip) edge between predecessor and successor
                actions.append(AddEdges(self.tracks, [(preds[0], succs[0])], {}))
            # if succs == 2, do nothing = the children already have different track ids

        # remove the nodes last
        actions.append(DeleteNodes(self.tracks, nodes))
        return ActionGroup(self.tracks, actions=actions)

    def update_nodes(
        self, nodes: np.ndarray[Any], attributes: dict[str, np.ndarray]
    ) -> None:
        """Calls the _update_nodes function to update the node attributtes in given array.
        Then calls the refresh signal.

        Args:
        nodes (np.ndarray[int]):an array of node ids
        attributes (dict[str, np.ndarray]): dictionary containing the attributes to be updated

        """

        action = self._update_nodes(nodes, attributes)
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit()

    def _update_nodes(
        self, nodes: np.ndarray[Any], attributes: dict[str, np.ndarray]
    ) -> TracksAction:
        """Update the attributes for the nodes in the given array.

        Args:
        nodes (np.ndarray[int]):an array of node ids
        attributes (dict[str, np.ndarray]): dictionary containing the attributes to be updated
        """
        return UpdateNodes(self.tracks, nodes, attributes)

    def add_edges(
        self, edges: np.ndarray[int], attributes: dict[str, np.ndarray]
    ) -> None:
        """Add edges and attributes to the graph. Also update the track ids and
        corresponding segmentations if applicable

        Args:
            edges (np.array[int]): An Nx2 array of N edges, each with source and target
                node ids
            attributes (dict[str, np.ndarray]): dictionary mapping attribute names to
                an array of values, where the index in the array matches the edge index
        """
        for edge in edges:
            if not self.is_valid(edge):
                # warning was printed with details in is_valid call
                return
        action = self._add_edges(edges, attributes)
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit()

    def _add_edges(
        self, edges: np.ndarray[int], attributes: dict[str, np.ndarray]
    ) -> TracksAction:
        """Add edges and attributes to the graph. Also update the track ids and
        corresponding segmentations if applicable

        Args:
            edges (np.array[int]): An Nx2 array of N edges, each with source and target
                node ids
            attributes (dict[str, np.ndarray]): dictionary mapping attribute names to
                an array of values, where the index in the array matches the edge index

        Returns:
            True if the edges were successfully added, False if any edge was invalid.
        """
        actions = [AddEdges(self.tracks, edges, attributes)]
        for edge in edges:
            out_degree = self.tracks.graph.out_degree(edge[0])
            if out_degree == 0:  # joining two segments
                # assign the track id of the source node to the target and all out
                # edges until end of track
                new_track_id = self.tracks.get_track_id(edge[0])
                actions.append(UpdateTrackID(self.tracks, edge[1], new_track_id))
            elif out_degree == 1:  # creating a division
                # assign a new track id to existing child
                successor = next(iter(self.tracks.graph.successors(edge[0])))
                actions.append(
                    UpdateTrackID(
                        self.tracks, successor, self.tracks.get_next_track_id()
                    )
                )
            else:
                raise RuntimeError(
                    f"Expected degree of 0 or 1 before adding edge, got {out_degree}"
                )
        return ActionGroup(self.tracks, actions)

    def is_valid(self, edge):
        """Check if this edge is valid.
        Criteria:
        - not horizontal
        - not existing yet
        - no merges
        - no triple divisions
        - new edge should be the shortest possible connection between two nodes, given their track_ids.
        (no skipping/bypassing any nodes of the same track_id). Check if there are any nodes of the same source or target track_id between source and target

        Args:
            edge (np.ndarray[(int, int)]: edge to be validated
        Returns:
            True if the edge is valid, false if invalid"""

        # make sure that the node2 is downstream of node1
        time1 = self.tracks.graph.nodes[edge[0]][NodeAttr.TIME.value]
        time2 = self.tracks.graph.nodes[edge[1]][NodeAttr.TIME.value]

        if time1 > time2:
            edge = (edge[1], edge[0])
            time1, time2 = time2, time1

        # do all checks
        # reject if edge already exists
        if self.tracks.graph.has_edge(edge[0], edge[1]):
            show_warning("Edge is rejected because it exists already.")
            return False

        # reject if edge is horizontal
        elif (
            self.tracks.graph.nodes[edge[0]][NodeAttr.TIME.value]
            == self.tracks.graph.nodes[edge[1]][NodeAttr.TIME.value]
        ):
            show_warning("Edge is rejected because it is horizontal.")
            return False

        # reject if target node already has an incoming edge
        elif self.tracks.graph.in_degree(edge[1]) > 0:
            msg = QMessageBox()
            msg.setWindowTitle("Delete existing edge?")
            msg.setText(
                "Creating this edge involves breaking an existing incoming edge to the target node. Proceed?"
            )
            msg.setIcon(QMessageBox.Information)

            # Set both OK and Cancel buttons
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

            # Execute the message box and catch the result
            result = msg.exec_()

            # Check which button was clicked
            if result == QMessageBox.Ok:
                print("User clicked OK")

                # identify incoming edge in the target node and insert a delete action
                pred = next(self.tracks.graph.predecessors(edge[1]))
                action = self._delete_edges(edges=np.array([[pred, edge[1]]]))
                self.action_history.append(action)
                action.apply()

            elif result == QMessageBox.Cancel:
                show_warning(
                    "Edge is rejected because merges are currently not allowed."
                )
                return False

        elif self.tracks.graph.out_degree(edge[0]) > 1:
            show_warning(
                "Edge is rejected because triple divisions are currently not allowed."
            )
            return False

        elif time2 - time1 > 1:
            track_id2 = self.tracks.graph.nodes[edge[1]][NodeAttr.TRACK_ID.value]
            # check whether there are already any nodes with the same track id between source and target (shortest path between equal track_ids rule)
            for t in range(time1 + 1, time2):
                nodes = [
                    n
                    for n, attr in self.tracks.graph.nodes(data=True)
                    if attr.get(NodeAttr.TIME.value) == t
                    and attr.get(NodeAttr.TRACK_ID.value) == track_id2
                ]
                if len(nodes) > 0:
                    show_warning("Please connect to the closest node")
                    return False

        # all checks passed!
        return True

    def delete_edges(self, edges: np.ndarray):
        """Delete edges from the graph.

        Args:
            edges (np.ndarray): _description_
        """

        for edge in edges:
            # First check if the to be deleted edges exist
            if not self.tracks.graph.has_edge(edge[0], edge[1]):
                show_warning("Cannot delete non-existing edge!")
                return
        action = self._delete_edges(edges)
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit()

    def _delete_edges(self, edges: np.ndarray) -> ActionGroup:
        actions = [DeleteEdges(self.tracks, edges)]
        for edge in edges:
            out_degree = self.tracks.graph.out_degree(edge[0])
            if out_degree == 1:  # removing a normal (non division) edge
                new_track_id = self.tracks.get_next_track_id()
                actions.append(UpdateTrackID(self.tracks, edge[1], new_track_id))
            elif out_degree == 2:  # removing a division edge
                sibling = next(
                    succ
                    for succ in self.tracks.graph.successors(edge[0])
                    if succ != edge[1]
                )
                new_track_id = self.tracks.get_track_id(edge[0])
                actions.append(UpdateTrackID(self.tracks, sibling, new_track_id))
            else:
                raise RuntimeError(
                    f"Expected degree of 1 or 2 before removing edge, got {out_degree}"
                )
        return ActionGroup(self.tracks, actions)

    def update_edges(self, edges: np.ndarray, attributes: Attributes):
        pass

    def update_segmentations(
        self,
        updated_pixels: list,
        current_timepoint: int,
    ) -> None:
        """Handle a change in the segmentation mask, checking for node addition, deletion, and attribute updates.
        Args:
            updated_pixels (list[(tuple(np.ndarray, np.ndarray, np.ndarray), np.ndarray, int)]): list holding the operations that updated the segmentation (directly from the napari labels paint event).
                Each element in the list consists of a tuple of np.ndarrays representing indices for each dimension, an array of the previous values, and an array or integer representing the new value(s)
            current_timepoint (int): the current time point in the viewer, used to set the selected node.
        """
        old_values = list(
            np.unique(np.concatenate([ev[1] for ev in updated_pixels]))
        )  # this is the full event and we need to store it in order to undo
        new_value = [updated_pixels[-1][-1]]

        # check which time points are affected (user might paint in 3 dimensions on 2D + time data)
        time_points = list(
            np.unique(np.concatenate([ev[0][0] for ev in updated_pixels]))
        )  # have to check the first array axis of the first element (the array) of all elements in event.value (just the last one is not always sufficient)

        changed_track_ids = old_values + new_value
        changed_track_ids = [value for value in changed_track_ids if value != 0]
        actions = []
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
                actions.append(self._delete_nodes(np.array(deleted)))

            # update node attributes in the graph
            if len(updated_nodes) > 0:
                for key in updated_node_attrs:
                    updated_node_attrs[key] = np.array(updated_node_attrs[key])
                actions.append(
                    self._update_nodes(np.array(updated_nodes), updated_node_attrs)
                )

            # add new nodes (and edges) to the graph
            if len(new_nodes) > 0:
                for key in new_node_attrs:
                    new_node_attrs[key] = np.array(new_node_attrs[key])
                actions.append(
                    self._add_nodes(
                        nodes=np.array(new_nodes),
                        attributes=new_node_attrs,
                    )
                )

            # if this is the time point where the user added a node, select the new node
            if t == current_timepoint:
                node_to_select = new_nodes[0] if new_nodes else None

        action_group = ActionGroup(self.tracks, actions, updated_pixels=updated_pixels)
        self.action_history.append(action_group)
        action_group.apply(
            apply_seg=False
        )  # do not apply the segmentation, as the user already did this! We only store it to be able to undo.
        self.tracks.refresh.emit(node_to_select)

    def add_node_attribute(self, name: str, values: any):
        pass

    def add_edge_attribute(self, name: str, values: any):
        pass

    def remove_node_attribute(self, name: str):
        pass

    def undo(self) -> None:
        """Obtain the action to undo from the history, and invert and apply it"""
        action_to_undo = self.action_history.previous()
        if action_to_undo is not None:
            inverse_action = action_to_undo.inverse()
            inverse_action.apply(apply_seg=True)
            self.tracks.refresh()

    def redo(self) -> None:
        """Obtain the action to redo from the history and apply it"""
        action_to_redo = self.action_history.next()
        if action_to_redo is not None:
            action_to_redo.apply(apply_seg=True)
            self.tracks.refresh()
