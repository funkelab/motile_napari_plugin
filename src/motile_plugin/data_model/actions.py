"""This module contains all the low level actions used to control a Tracks object.
Low level actions should control these aspects of Tracks:
    - synchronizing segmentation and nodes (including bi-directional access). Currently,
    this means updating the seg_id and time attributes on the node, and updating the
    seg_time_to_node dictionary.
    - Updating attributes that are controlled by the segmentation. Currently, position
    and area for nodes, and IOU for edges.
    - Keeping track of information needed to undo the given action. For removing a node,
    this means keeping track of the incident edges that were removed, along with their
    attributes.

The low level actions do not contain application logic, such as manipulating track ids,
or validation of "allowed" actions.
The actions should work on candidate graphs as well as solution graphs.
Action groups can be constructed to represent application-level actions constructed
from many low-level actions.
"""

from __future__ import annotations

from typing import Any

from motile_toolbox.candidate_graph.graph_attributes import NodeAttr

from .tracks import Attributes, Edge, Node, SegMask, Tracks


class TracksAction:
    def __init__(self, tracks: Tracks):
        """An modular change that can be applied to the given Tracks. The tracks must
        be passed in at construction time so that metadata needed to invert the action
        can be extracted.

        Args:
            tracks (Tracks): The tracks that this action will edit
        """
        self.tracks = tracks

    def inverse(self) -> TracksAction:
        """Get the inverse action of this action. Can be used to undo and redo an action.

        Raises:
            NotImplementedError: if the inverse is not implemented in the subclass

        Returns:
            TracksAction: An action that un-does this action, bringing the tracks
                back to the exact state it had before applying this action.
        """
        raise NotImplementedError("Inverse not implemented")

    def apply(self):
        """Apply this action to the tracks object stored in the action.

        Raises:
            NotImplementedError: if the apply function is not implemented in the subclass
        """
        raise NotImplementedError("Apply not implemented")


class ActionGroup(TracksAction):
    def __init__(
        self,
        tracks: Tracks,
        actions: list[TracksAction],
    ):
        """A group of actions that is also an action, used to modify the given tracks.
        This is useful for creating composite actions from the low-level actions.
        Composite actions can contain application logic and can be un-done as a group.

        Args:
            tracks (Tracks): The tracks that this action will edit
            actions (list[TracksAction]): A list of actions contained within the group,
                in the order in which they should be executed.
        """
        super().__init__(tracks)
        self.actions = actions

    def inverse(self) -> ActionGroup:
        actions = [action.inverse() for action in self.actions[::-1]]
        return ActionGroup(self.tracks, actions)

    def apply(self):
        for action in self.actions:
            action.apply()


class AddNodes(TracksAction):
    """Action for adding new nodes. If a segmentation should also be added, the
    pixels for each node should be provided. The label to set the pixels will
    be taken from the seg_id attribute. The existing pixel values are assumed to be
    zero - you must explicitly update any other segmentations that were overwritten
    using an UpdateNodes action if you want to be able to undo the action.

    """

    def __init__(
        self,
        tracks: Tracks,
        nodes: list[Node],
        attributes: dict[str, list[Any]],
        pixels: list[SegMask] | None = None,
    ):
        """Create an action to add new nodes, with optional segmentation

        Args:
            tracks (Tracks): The Tracks to add the n
            nodes (Node): _description_
            attributes (dict[str, list[Any]]): _description_
            pixels (list | None, optional): _description_. Defaults to None.
        """
        super().__init__(tracks)
        self.nodes = nodes
        self.attributes = attributes
        self.pixels = pixels

    def inverse(self):
        """Invert the action to delete nodes instead"""
        return DeleteNodes(self.tracks, self.nodes)

    def apply(self):
        """Apply the action, and set segmentation if provided in self.pixels"""
        for idx, node in enumerate(self.nodes):
            attrs = {attr: val[idx] for attr, val in self.attributes.items()}
            seg_id = attrs.get(NodeAttr.SEG_ID.value, None)
            if self.pixels is not None and self.pixels[idx] is not None:
                assert (
                    seg_id is not None
                ), f"Could not get seg_id to set pixels to for new node {node}"
                self.tracks.set_pixels(self.pixels[idx], seg_id)
            time = attrs[self.tracks.time_attr]
            pos = attrs[self.tracks.pos_attr]
            self.tracks.add_node(node, time, position=pos, seg_id=seg_id, attrs=attrs)


class DeleteNodes(TracksAction):
    """Action of deleting existing nodes
    If the tracks contain a segmentation, this action also constructs a reversible
    operation for setting involved pixels to zero
    """

    def __init__(self, tracks: Tracks, nodes: list[Node], pixels: list[SegMask] | None):
        super().__init__(tracks)
        self.nodes = nodes
        self.attributes = self.tracks.get_node_attributes(nodes)
        self.pixels = self.tracks.get_pixels(nodes) if pixels is None else pixels
        self.tracks = tracks

    def inverse(self):
        """Invert this action, and provide inverse segmentation operation if given"""

        return AddNodes(self.tracks, self.nodes, self.attributes, pixels=self.pixels)

    def apply(self):
        """ASSUMES THERE ARE NO INCIDENT EDGES - raises valueerror if an edge will be removed
        by this operation
        Steps:
        - For each node
            set pixels to 0 if self.pixels is provided
        - Remove nodes from graph
        """
        for idx, node in enumerate(self.nodes):
            if self.pixels is not None:
                self.tracks.set_pixels(self.pixels[idx], 0)
            self.tracks.remove_node(node)


class UpdateNodes(TracksAction):
    """Action for updating the attributes of nodes, including the segmentation"""

    def __init__(
        self,
        tracks: Tracks,
        nodes: list[Node],
        attributes: Attributes,
        pixels: list[SegMask] | None = None,
        added: bool = True,
    ):
        super().__init__(tracks)
        self.nodes = nodes
        self.old_attrs = self.tracks.get_node_attributes(nodes)
        self.new_attrs = attributes
        self.pixels = pixels
        self.added = added

    def inverse(self):
        """Restore previous attributes"""
        return UpdateNodes(
            self.tracks,
            self.nodes,
            attributes=self.old_attrs,
            pixels=self.pixels,
            added=not self.added,
        )

    def apply(self):
        """Set new attributes"""
        self.tracks.set_node_attributes(self.nodes, self.new_attrs)
        if self.pixels is not None:
            for node, pix in zip(self.nodes, self.pixels, strict=False):
                if pix is not None:
                    self.tracks.update_segmentation(node, pix, self.added)


class AddEdges(TracksAction):
    """Action for adding new edges"""

    def __init__(self, tracks: Tracks, edges: list[Edge], attributes: Attributes):
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
            self.tracks.add_edge(edge, attrs)


class UpdateTrackID(TracksAction):
    def __init__(self, tracks: Tracks, start_node: Node, track_id: int):
        """Args:
        tracks (Tracks): The tracks to update
        start_node (Any): The node ID of the first node in the track. All successors
            with the same track id as this node will be updated.
        track_id (int): The new track id to assign.
        """
        super().__init__(tracks)
        self.start_node = start_node
        self.old_track_id = self.tracks.get_seg_id(start_node)
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
            self.tracks.set_track_id(curr_node, self.new_track_id)
            if self.tracks.segmentation is not None:
                time = self.tracks.get_time(curr_node)
                # update the segmentation to match the new track id
                self.tracks.change_segmentation_label(
                    time, old_track_id, self.new_track_id
                )
                # update the graph seg_id attr to match the new seg id
                self.tracks.set_seg_id(curr_node, self.new_track_id)
            # getting the next node (picks one if there are two)
            successors = list(self.tracks.graph.successors(curr_node))
            if len(successors) == 0:
                break
            curr_node = successors[0]


class DeleteEdges(TracksAction):
    """Action for deleting edges"""

    def __init__(self, tracks: Tracks, edges: list[Edge]):
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

    def __init__(self, tracks: Tracks, edges: list[Edge], attributes: Attributes):
        super().__init__(tracks)
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
