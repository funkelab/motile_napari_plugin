from __future__ import annotations

import numpy as np
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr

from .tracks import Tracks


class TracksAction:
    def __init__(self, tracks: Tracks):
        self.tracks = tracks

    def inverse(self) -> TracksAction:
        raise NotImplementedError("Inverse not implemented")

    def apply(self):
        raise NotImplementedError("Apply not implemented")


class ActionGroup(TracksAction):
    """Handles the inverting and applying of a group of TracksActions. If the actiongroup involves a change in the segmentation, they are stored in the updated_pixels list, which consists of operations, consisting of a tuple of indices for all dimensions, an array of the previous values, and an array or integer representing the new value(s)"""

    def __init__(
        self,
        tracks: Tracks,
        actions: list[TracksAction],
        updated_pixels: list | None = None,  # [(tuple(np.array), np.array, int)]
    ):
        super().__init__(tracks)
        self.actions = actions
        self.updated_pixels = updated_pixels

    def inverse(self) -> ActionGroup:
        """Invert all actions in he list, and invert the segmentation operation"""

        actions = [action.inverse() for action in self.actions[::-1]]
        if self.updated_pixels is not None:
            inverse_seg = []
            for prev_indices, prev_values, next_values in self.updated_pixels:
                inverse_seg.append([prev_indices, next_values, prev_values])
        else:
            inverse_seg = None

        return ActionGroup(self.tracks, actions, updated_pixels=inverse_seg)

    def apply(self, apply_seg: bool | None = False):
        """Apply the actions and apply the segmentation update"""

        for action in self.actions:
            action.apply()
        if apply_seg and self.updated_pixels is not None:
            self.tracks.update_segmentation(self.updated_pixels)


class AddNodes(TracksAction):
    """Action for adding new nodes
    In the case nodes need to be restored, the operation for this is provided by the updated_pixels attribute
    """

    def __init__(
        self, tracks: Tracks, nodes, attributes, updated_pixels: list | None = None
    ):
        super().__init__(tracks)
        self.tracks = tracks
        self.nodes = nodes
        self.attributes = attributes
        self.updated_pixels = updated_pixels

    def inverse(self):
        """Invert the action to delete nodes instead"""

        return DeleteNodes(self.tracks, self.nodes)

    def apply(self):
        """Apply the action, and restore segmentation if provided in self.updated_pixels"""

        if self.updated_pixels is not None:
            self.tracks.update_segmentation(self.updated_pixels)
        for idx, node in enumerate(self.nodes):
            attrs = {attr: val[idx] for attr, val in self.attributes.items()}
            self.tracks.graph.add_node(node, **attrs)
            track_id = attrs[NodeAttr.TRACK_ID.value]
            self.tracks.node_id_to_track_id[node] = track_id


class DeleteNodes(TracksAction):
    """Action of deleting existing nodes
    If the tracks contain a segmentation, this action also constructs a reversible operation for setting involved pixels to zero
    """

    def __init__(self, tracks: Tracks, nodes):
        super().__init__(tracks)
        self.nodes = nodes
        self.attributes = self.tracks.get_node_attributes(nodes)
        self.tracks = tracks
        if self.tracks.segmentation is not None:
            # construct reversible operation for setting involved pixels to 0
            self.updated_pixels = []
            for node in self.nodes:
                time = self.tracks.get_time(node)
                track_id = self.tracks.get_track_id(node)

                # get all indices where the segmentation label == track_id
                indices = np.where(self.tracks.segmentation == track_id)

                # filter by time: we only want to delete the segmentation for one node, at given time
                mask = indices[0] == time
                indices = tuple(arr[mask] for arr in indices)

                # construct the operation (indices, prev_values, new_values)
                prev_values = track_id
                new_values = 0
                operation = (indices, prev_values, new_values)
                self.updated_pixels.append(operation)
        else:
            self.updated_pixels = None

    def inverse(self):
        """Invert this action, and provide inverse segmentation operation if given"""

        if self.updated_pixels is not None:
            inverse_seg = []
            for prev_indices, prev_values, next_values in self.updated_pixels:
                inverse_seg.append([prev_indices, next_values, prev_values])
        else:
            inverse_seg = None

        return AddNodes(self.tracks, self.nodes, self.attributes, inverse_seg)

    def apply(self):
        """ASSUMES THERE ARE NO INCIDENT EDGES - raises valueerror if an edge will be removed
        by this operation
        Steps:
        - For each node
            execute update_segmentation if an operation is provided in self.update_pixels
        - Remove nodes from graph
        """
        for node in self.nodes:
            if self.tracks.segmentation is not None and self.updated_pixels is not None:
                self.tracks.update_segmentation(self.updated_pixels)
            self.tracks.graph.remove_node(node)
            del self.tracks.node_id_to_track_id[node]


class UpdateNodes(TracksAction):
    """Action for updating the attributes of nodes"""

    def __init__(self, tracks: Tracks, nodes, attributes):
        super().__init__(tracks)
        self.nodes = nodes
        self.old_attrs = self.tracks.get_node_attributes(nodes)
        self.new_attrs = attributes

    def inverse(self):
        """Restore previous attributes"""
        return UpdateNodes(self.tracks, self.nodes, attributes=self.old_attrs)

    def apply(self):
        """Set new attributes"""
        self.tracks.set_node_attributes(self.nodes, self.new_attrs)


class AddEdges(TracksAction):
    """Action for adding new edges"""

    def __init__(self, tracks: Tracks, edges, attributes):
        super().__init__(tracks)
        self.edges = edges
        self.attributes = attributes

    def inverse(self):
        """Delete edges"""
        return DeleteEdges(self.tracks, self.edges)

    def apply(self):
        """
        Steps:
        - add each edge to the graph. Assumes all edges are valid (they should be checked at this point already)
        """
        for idx, edge in enumerate(self.edges):
            attrs = {attr: val[idx] for attr, val in self.attributes.items()}
            self.tracks.graph.add_edge(edge[0], edge[1], **attrs)


class UpdateTrackID(TracksAction):
    def __init__(self, tracks: Tracks, start_node, track_id: int):
        """Args:
        tracks (Tracks): The tracks to update
        start_node (Any): The node ID of the first node in the track. All successors
            with the same track id as this node will be updated.
        track_id (int): The new track id to assign.
        """
        super().__init__(tracks)
        self.start_node = start_node
        self.old_track_id = self.tracks.get_track_id(start_node)
        self.new_track_id = track_id

    def inverse(self) -> TracksAction:
        """Restore the previous track_id"""
        return UpdateTrackID(self.tracks, self.start_node, self.old_track_id)

    def apply(self):
        """Assign a new track id to the track starting with start_node.
        Will also update the self.tracks.segmentation array and seg_id on the
        self.tracks.graph if a segmentation exists.
        """
        old_track_id = self.tracks.get_track_id(self.start_node)
        curr_node = self.start_node
        while self.tracks.get_track_id(curr_node) == old_track_id:
            # update the track id
            self.tracks.graph.nodes[curr_node][NodeAttr.TRACK_ID.value] = (
                self.new_track_id
            )
            self.tracks.node_id_to_track_id[curr_node] = self.new_track_id
            if self.tracks.segmentation is not None:
                time = self.tracks.get_time(curr_node)
                # update the segmentation to match the new track id
                self.tracks.change_segmentation_label(
                    time, old_track_id, self.new_track_id
                )
                # update the graph seg_id attr to match the new seg id
                self.tracks.graph.nodes[curr_node][NodeAttr.SEG_ID.value] = (
                    self.new_track_id
                )
            # getting the next node (picks one if there are two)
            successors = list(self.tracks.graph.successors(curr_node))
            if len(successors) == 0:
                break
            curr_node = successors[0]


class DeleteEdges(TracksAction):
    """Action for deleting edges"""

    def __init__(self, tracks: Tracks, edges):
        super().__init__(tracks)
        self.edges = edges
        self.attributes = tracks.get_edge_attributes(self.edges)

    def inverse(self):
        """Restore edges and their attributes"""
        return AddEdges(self.tracks, self.edges, self.attributes)

    def apply(self):
        """Steps:
        - Remove the edges from the graph
        """
        self.tracks.graph.remove_edges_from(self.edges)


class UpdateEdges(TracksAction):
    """Action to update the attributes of edges"""

    def __init__(self, tracks: Tracks, edges, attributes):
        super().__init__(UpdateEdges.__name__, tracks)
        self.edges = edges
        self.old_attrs = tracks.get_edge_attributes(self.edges)
        self.new_attrs = attributes

    def inverse(self):
        """Restore previous attributes"""
        return UpdateEdges(self.tracks, self.edges, self.old_attrs)

    def apply(self):
        """Steps:
        - update the attributes of all edges to the new values
        """
        self.tracks.set_edge_attributes(self.edges, self.new_attrs)
