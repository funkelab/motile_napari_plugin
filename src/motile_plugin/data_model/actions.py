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

from typing import TYPE_CHECKING, Any

from motile_toolbox.candidate_graph.graph_attributes import NodeAttr

from .tracks import Attrs, Edge, Node, SegMask, Tracks

if TYPE_CHECKING:
    from .solution_tracks import SolutionTracks


class TracksAction:
    def __init__(self, tracks: Tracks):
        """An modular change that can be applied to the given Tracks. The tracks must
        be passed in at construction time so that metadata needed to invert the action
        can be extracted.
        The change should be actually applied in the init function.

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
            attributes (dict[str, list[Any]]): Includes times, positions, and seg_ids
            pixels (list | None, optional): _description_. Defaults to None.
        """
        super().__init__(tracks)
        self.nodes = nodes
        user_attrs = attributes.copy()
        self.times = attributes.get(tracks.time_attr, None)
        if tracks.time_attr in attributes:
            del user_attrs[tracks.time_attr]
        self.positions = attributes.get(tracks.pos_attr, None)
        if tracks.pos_attr in attributes:
            del user_attrs[tracks.pos_attr]
        self.seg_ids = attributes.get(NodeAttr.SEG_ID.value, None)
        if NodeAttr.SEG_ID.value in attributes:
            del user_attrs[NodeAttr.SEG_ID.value]
        self.pixels = pixels
        self.attributes = user_attrs
        self._apply()

    def inverse(self):
        """Invert the action to delete nodes instead"""
        return DeleteNodes(self.tracks, self.nodes)

    def _apply(self):
        """Apply the action, and set segmentation if provided in self.pixels"""
        if self.pixels is not None:
            self.tracks.set_pixels(self.pixels, self.seg_ids)
        self.tracks.add_nodes(
            self.nodes, self.times, self.positions, self.seg_ids, attrs=self.attributes
        )


class DeleteNodes(TracksAction):
    """Action of deleting existing nodes
    If the tracks contain a segmentation, this action also constructs a reversible
    operation for setting involved pixels to zero
    """

    def __init__(
        self, tracks: Tracks, nodes: list[Node], pixels: list[SegMask] | None = None
    ):
        super().__init__(tracks)
        self.nodes = nodes
        self.attributes = {
            self.tracks.time_attr: self.tracks.get_times(nodes),
            self.tracks.pos_attr: self.tracks.get_positions(nodes),
            NodeAttr.SEG_ID.value: self.tracks.get_seg_ids(nodes),
            NodeAttr.TRACK_ID.value: self.tracks._get_nodes_attr(
                nodes, NodeAttr.TRACK_ID.value
            ),
        }
        self.pixels = self.tracks.get_pixels(nodes) if pixels is None else pixels
        self._apply()

    def inverse(self):
        """Invert this action, and provide inverse segmentation operation if given"""

        return AddNodes(self.tracks, self.nodes, self.attributes, pixels=self.pixels)

    def _apply(self):
        """ASSUMES THERE ARE NO INCIDENT EDGES - raises valueerror if an edge will be removed
        by this operation
        Steps:
        - For each node
            set pixels to 0 if self.pixels is provided
        - Remove nodes from graph
        """
        if self.pixels is not None:
            self.tracks.set_pixels(
                self.pixels,
                [
                    0,
                ]
                * len(self.pixels),
            )
        self.tracks.remove_nodes(self.nodes)


class UpdateNodeSegs(TracksAction):
    """Action for updating the segmentation associated with nodes"""

    def __init__(
        self,
        tracks: Tracks,
        nodes: list[Node],
        pixels: list[SegMask],
        added: bool = True,
    ):
        super().__init__(tracks)
        self.nodes = nodes
        self.pixels = pixels
        self.added = added
        self._apply()

    def inverse(self):
        """Restore previous attributes"""
        return UpdateNodeSegs(
            self.tracks,
            self.nodes,
            pixels=self.pixels,
            added=not self.added,
        )

    def _apply(self):
        """Set new attributes"""
        self.tracks.update_segmentations(self.nodes, self.pixels, self.added)


class UpdateNodeAttrs(TracksAction):
    """Action for updating the segmentation associated with nodes"""

    def __init__(
        self,
        tracks: Tracks,
        nodes: list[Node],
        attrs: Attrs,
    ):
        super().__init__(tracks)
        protected_attrs = [
            NodeAttr.TIME.value,
            NodeAttr.AREA.value,
            NodeAttr.SEG_ID.value,
            NodeAttr.TRACK_ID.value,
        ]
        for attr in attrs:
            if attr in protected_attrs:
                raise ValueError(f"Cannot update attribute {attr} manually")
        self.nodes = nodes
        self.prev_attrs = {
            attr: self.tracks._get_nodes_attr(nodes, attr) for attr in attrs
        }
        self.new_attrs = attrs
        self._apply()

    def inverse(self):
        """Restore previous attributes"""
        return UpdateNodeAttrs(
            self.tracks,
            self.nodes,
            self.prev_attrs,
        )

    def _apply(self):
        """Set new attributes"""
        for attr, values in self.new_attrs.items():
            self.tracks._set_nodes_attr(self.nodes, attr, values)


class AddEdges(TracksAction):
    """Action for adding new edges"""

    def __init__(self, tracks: Tracks, edges: list[Edge]):
        super().__init__(tracks)
        self.edges = edges
        self._apply()

    def inverse(self):
        """Delete edges"""
        return DeleteEdges(self.tracks, self.edges)

    def _apply(self):
        """
        Steps:
        - add each edge to the graph. Assumes all edges are valid (they should be checked at this point already)
        """
        self.tracks.add_edges(self.edges)


class DeleteEdges(TracksAction):
    """Action for deleting edges"""

    def __init__(self, tracks: Tracks, edges: list[Edge]):
        super().__init__(tracks)
        self.edges = edges
        self._apply()

    def inverse(self):
        """Restore edges and their attributes"""
        return AddEdges(self.tracks, self.edges)

    def _apply(self):
        """Steps:
        - Remove the edges from the graph
        """
        self.tracks.remove_edges(self.edges)


class UpdateTrackID(TracksAction):
    def __init__(self, tracks: SolutionTracks, start_node: Node, track_id: int):
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
        self._apply()

    def inverse(self) -> TracksAction:
        """Restore the previous track_id"""
        return UpdateTrackID(self.tracks, self.start_node, self.old_track_id)

    def _apply(self):
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
                # update the segmentation to match the new track id
                pix = self.tracks.get_pixels([curr_node])
                self.tracks.set_pixels(pix, [self.new_track_id])
                # update the graph seg_id attr to match the new seg id
                self.tracks.set_seg_id(curr_node, self.new_track_id)
            # getting the next node (picks one if there are two)
            successors = list(self.tracks.graph.successors(curr_node))
            if len(successors) == 0:
                break
            curr_node = successors[0]
