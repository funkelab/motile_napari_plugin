from typing import Any

import numpy as np
from motile_toolbox.candidate_graph import NodeAttr
from napari.utils.notifications import show_warning
from qtpy.QtWidgets import QMessageBox

from .action_history import ActionHistory
from .actions import (
    ActionGroup,
    AddEdges,
    AddNodes,
    DeleteEdges,
    DeleteNodes,
    TracksAction,
    UpdateNodeSegs,
    UpdateTrackID,
)
from .solution_tracks import SolutionTracks
from .tracks import Attrs, Node, SegMask


class TracksController:
    """A set of high level functions to change the data model.
    All changes to the data should go through this API.
    """

    def __init__(self, tracks: SolutionTracks):
        self.tracks = tracks
        self.action_history = ActionHistory()
        self.node_id_counter = 1

    def add_nodes(
        self,
        attributes: Attrs,
        pixels: list[SegMask] | None = None,
    ) -> None:
        """Calls the _add_nodes function to add nodes. Calls the refresh signal when finished.

        Args:
            nodes (np.ndarray[int]):an array of node ids
            attributes (dict[str, np.ndarray]): dictionary containing at least time and position attributes
        """
        action, nodes = self._add_nodes(attributes, pixels)
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit(nodes[0] if nodes else None)

    def _add_nodes(
        self,
        attributes: Attrs,
        pixels: list[SegMask] | None = None,
    ) -> tuple[TracksAction, list[Node]]:
        """Add nodes to the graph. Includes all attributes and the segmentation.
        If there is a segmentation, the attributes must include:
        - time
        - seg_id
        - track_id
        If there is not a segmentation, the attributes must include:
        - time
        - pos
        - track_id

        Args:
            nodes (list[Node]): a list of node ids
            attributes (Attributes): dictionary containing at least time and track id,
                and either seg_id (if pixels are provided) or position (if not)
            pixels (list[SegMask] | None): A list of pixels associated with the node,
                or None if there is no segmentation. These pixels will be updated
                in the tracks.segmentation, set to the provided seg_id
        """
        times = attributes[NodeAttr.TIME.value]
        if len(times) == 0:
            raise ValueError("Cannot add nodes without times")
        nodes = self._get_new_node_ids(len(times))
        actions = [
            AddNodes(
                tracks=self.tracks,
                nodes=nodes,
                attributes=attributes,
                pixels=pixels,
            )
        ]
        for idx, node in enumerate(nodes):
            current_time = attributes[self.tracks.time_attr][idx]
            track_id = attributes[NodeAttr.TRACK_ID.value][idx]
            if track_id in list(self.tracks.node_id_to_track_id.values()):
                # this track_id already exists, find the nearest predecessor and nearest successor to create new edge
                candidates = [
                    node
                    for node, tid in self.tracks.node_id_to_track_id.items()
                    if tid == track_id
                ]

                # Sort candidates by their 'time' attribute
                candidates.sort(key=lambda n: self.tracks.get_time(n))
                closest_predecessor = None
                closest_successor = None

                for candidate in candidates:
                    candidate_time = self.tracks.get_time(candidate)
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
                    actions.append(AddEdges(self.tracks, [(closest_predecessor, node)]))
                if closest_successor is not None and not self.tracks.graph.has_edge(
                    node, closest_successor
                ):
                    actions.append(AddEdges(self.tracks, [(node, closest_successor)]))

        return ActionGroup(self.tracks, actions), nodes

    def delete_nodes(self, nodes: np.ndarray[Any]) -> None:
        """Calls the _delete_nodes function and then emits the refresh signal

        Args:
            nodes (np.ndarray): array of node_ids to be deleted
        """

        action = self._delete_nodes(nodes)
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit()

    def _delete_nodes(
        self, nodes: np.ndarray[Any], pixels: list[SegMask] | None = None
    ) -> TracksAction:
        """Delete the nodes provided by the array from the graph but maintain successor
        track_ids. Reconnect to the nearest predecessor and/or nearest successor
        on the same track, if any.

        Args:
            nodes (np.ndarray): array of node_ids to be deleted
        """
        actions = []
        for node in nodes:
            preds = list(self.tracks.graph.predecessors(node))
            succs = list(self.tracks.graph.successors(node))

            # remove incident edges in an undo-able fashion
            for pred in preds:
                actions.append(DeleteEdges(self.tracks, [(pred, node)]))
            for succ in succs:
                actions.append(DeleteEdges(self.tracks, [(node, succ)]))

            if len(preds) == 0:  # do nothing - track ids are fine
                continue
            pred = preds[0]  # assume can't have two preds, no merging (yet)

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
                actions.append(AddEdges(self.tracks, [(preds[0], succs[0])]))
            # if succs == 2, do nothing = the children already have different track ids

        # remove the nodes last
        actions.append(DeleteNodes(self.tracks, nodes, pixels=pixels))
        return ActionGroup(self.tracks, actions=actions)

    def update_node_segs(
        self, nodes: np.ndarray[Any], attributes: dict[str, np.ndarray]
    ) -> None:
        """Calls the _update_node_segs function to update the node attributtes in given array.
        Then calls the refresh signal.

        Args:
        nodes (np.ndarray[int]):an array of node ids
        attributes (dict[str, np.ndarray]): dictionary containing the attributes to be updated

        """
        action = self._update_node_segs(nodes, attributes)
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit()

    def _update_node_segs(
        self,
        nodes: np.ndarray[Any],
        pixels: list[SegMask],
        added=False,
    ) -> TracksAction:
        """Update the segmentation and segmentation-managed attributes for
        a set of nodes.

        Args:
        nodes (np.ndarray[int]):an array of node ids
        attributes (dict[str, np.ndarray]): dictionary containing the attributes to be updated
        """
        return UpdateNodeSegs(self.tracks, nodes, pixels, added=added)

    def add_edges(self, edges: np.ndarray[int]) -> None:
        """Add edges and attributes to the graph. Also update the track ids and
        corresponding segmentations if applicable

        Args:
            edges (np.array[int]): An Nx2 array of N edges, each with source and target
                node ids
        """
        make_valid_actions = []
        for edge in edges:
            is_valid, valid_action = self.is_valid(edge)
            if not is_valid:
                # warning was printed with details in is_valid call
                return
            if valid_action is not None:
                make_valid_actions.append(valid_action)
        main_action = self._add_edges(edges)
        if len(make_valid_actions) > 0:
            make_valid_actions.append(main_action)
            action = ActionGroup(self.tracks, make_valid_actions)
        else:
            action = main_action
        self.action_history.append(action)
        action.apply()
        self.tracks.refresh.emit()

    def _add_edges(self, edges: np.ndarray[int]) -> TracksAction:
        """Add edges and attributes to the graph. Also update the track ids and
        corresponding segmentations of the target node tracks and potentially sibling
        tracks.

        Args:
            edges (np.array[int]): An Nx2 array of N edges, each with source and target
                node ids
            attributes (dict[str, np.ndarray]): dictionary mapping attribute names to
                an array of values, where the index in the array matches the edge index

        Returns:
            True if the edges were successfully added, False if any edge was invalid.
        """
        actions = [AddEdges(self.tracks, edges)]
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

    def is_valid(self, edge) -> tuple[bool, TracksAction | None]:
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
        action = None
        # do all checks
        # reject if edge already exists
        if self.tracks.graph.has_edge(edge[0], edge[1]):
            show_warning("Edge is rejected because it exists already.")
            return False, action

        # reject if edge is horizontal
        elif (
            self.tracks.graph.nodes[edge[0]][NodeAttr.TIME.value]
            == self.tracks.graph.nodes[edge[1]][NodeAttr.TIME.value]
        ):
            show_warning("Edge is rejected because it is horizontal.")
            return False, action

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

            elif result == QMessageBox.Cancel:
                show_warning(
                    "Edge is rejected because merges are currently not allowed."
                )
                return False, action

        elif self.tracks.graph.out_degree(edge[0]) > 1:
            show_warning(
                "Edge is rejected because triple divisions are currently not allowed."
            )
            return False, action

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
                    return False, action

        # all checks passed!
        return True, action

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
        print("delete these edges", edges)
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
                print("new track id is ", new_track_id)
                actions.append(UpdateTrackID(self.tracks, edge[1], new_track_id))
            elif out_degree == 2:  # removing a division edge
                sibling = next(
                    succ
                    for succ in self.tracks.graph.successors(edge[0])
                    if succ != edge[1]
                )
                new_track_id = self.tracks.get_track_id(edge[0])
                print("new track id", new_track_id)
                actions.append(UpdateTrackID(self.tracks, sibling, new_track_id))
            else:
                raise RuntimeError(
                    f"Expected degree of 1 or 2 before removing edge, got {out_degree}"
                )
        return ActionGroup(self.tracks, actions)

    def update_edges(self, edges: np.ndarray, attributes: Attrs):
        pass

    def update_segmentations(
        self,
        to_remove: list[Node],  # (node_ids, pixels)
        to_update_smaller: list[tuple],  # (node_id, pixels)
        to_update_bigger: list[tuple],  # (node_id, pixels)
        to_add: list[tuple],  # (track_id, pixels)
        current_timepoint: int,
    ) -> None:
        """Handle a change in the segmentation mask, checking for node addition, deletion, and attribute updates.
        Args:
            updated_pixels (list[(tuple(np.ndarray, np.ndarray, np.ndarray), np.ndarray, int)]):
                list holding the operations that updated the segmentation (directly from
                the napari labels paint event).
                Each element in the list consists of a tuple of np.ndarrays representing
                indices for each dimension, an array of the previous values, and an array
                or integer representing the new value(s)
            current_timepoint (int): the current time point in the viewer, used to set the selected node.
        """
        actions = []
        node_to_select = None
        if len(to_remove) > 0:
            nodes = [node_id for node_id, _ in to_remove]
            pixels = [pixels for _, pixels in to_remove]
            actions.append(self._delete_nodes(nodes, pixels=pixels))
        if len(to_update_smaller) > 0:
            nodes = [node_id for node_id, _ in to_update_smaller]
            pixels = [pixels for _, pixels in to_update_smaller]
            actions.append(self._update_node_segs(nodes, pixels, added=False))
        if len(to_update_bigger) > 0:
            nodes = [node_id for node_id, _ in to_update_bigger]
            pixels = [pixels for _, pixels in to_update_bigger]
            actions.append(self._update_node_segs(nodes, pixels, added=True))
        if len(to_add) > 0:
            nodes = [node for node, _ in to_add]
            pixels = [pix for _, pix in to_add]
            seg_ids = [val for val, _ in to_add]
            times = [pix[0][0] for pix in pixels]
            attributes = {
                NodeAttr.SEG_ID.value: seg_ids,
                NodeAttr.TRACK_ID.value: seg_ids,
                self.tracks.time_attr: times,
            }
            action, nodes = self._add_nodes(attributes=attributes, pixels=pixels)
            actions.append(action)

            # if this is the time point where the user added a node, select the new node
            if current_timepoint in times:
                index = times.index(current_timepoint)
                node_to_select = nodes[index]

        action_group = ActionGroup(self.tracks, actions)
        self.action_history.append(action_group)
        action_group.apply()
        self.tracks.refresh.emit(node_to_select)

    def undo(self) -> None:
        """Obtain the action to undo from the history, and invert and apply it"""
        action_to_undo = self.action_history.previous()
        if action_to_undo is not None:
            inverse_action = action_to_undo.inverse()
            inverse_action.apply()
            self.tracks.refresh()

    def redo(self) -> None:
        """Obtain the action to redo from the history and apply it"""
        action_to_redo = self.action_history.next()
        if action_to_redo is not None:
            action_to_redo.apply()
            self.tracks.refresh()

    def _get_new_node_ids(self, n: int) -> list[Node]:
        """Get a list of new node ids for creating new nodes.
        They will be unique from all existing nodes, but have no other guarantees.

        Args:
            n (int): The number of new node ids to return

        Returns:
            list[Node]: A list of new node ids.
        """
        ids = [self.node_id_counter + i for i in range(n)]
        self.node_id_counter += n
        for idx, _id in enumerate(ids):
            while self.tracks.graph.has_node(_id):
                self.node_id_counter += 1
                _id = self.node_id_counter
            ids[idx] = _id
        return ids
