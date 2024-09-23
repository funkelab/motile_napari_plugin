from __future__ import annotations

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
    def __init__(self, tracks: Tracks, actions: list[TracksAction]):
        super().__init__(tracks)
        self.actions = actions

    def inverse(self) -> ActionGroup:
        actions = [action.inverse() for action in self.actions[::-1]]
        return ActionGroup(self.tracks, actions)

    def apply(self):
        for action in self.actions:
            action.apply()


class AddNodes(TracksAction):
    def __init__(self, tracks: Tracks, nodes, attributes, segmentations):
        super().__init__(tracks)
        self.nodes = nodes
        self.attributes = attributes
        self.segmentations = segmentations

    def inverse(self):
        return DeleteNodes(self.nodes)

    def apply(self):
        for idx, node in enumerate(self.nodes):
            attrs = {attr: val[idx] for attr, val in self.attributes.items()}
            self.tracks.graph.add_node(node, **attrs)

            track_id = attrs[NodeAttr.TRACK_ID.value]
            self.tracks.node_id_to_track_id[node] = track_id


class DeleteNodes(TracksAction):
    def __init__(self, tracks: Tracks, nodes):
        super().__init__(tracks)
        self.nodes = nodes
        self.attributes = tracks.get_node_attributes(nodes)
        self.segmentations = tracks.get_segmentations(nodes)

    def inverse(self):
        return AddNodes(self.tracks, self.nodes, self.attributes, self.segmentations)

    def apply(self):
        """ASSUMES THERE ARE NO INCIDENT EDGES - raises valueerror if an edge will be removed
        by this operation
        Steps:
        - For each node
            * remove segmentations if present
        - Remove nodes from graph
        """
        for node in self.nodes:
            if self.tracks.segmentation is not None:
                self.tracks.delete_segmentation(node)
            self.tracks.graph.remove_node(node)
            del self.tracks.node_id_to_track_id[node]


class UpdateNodes(TracksAction):
    def __init__(self, tracks: Tracks, nodes, attributes):
        super().__init__(tracks)
        self.nodes = nodes
        self.old_attrs = self.tracks.get_node_attributes(nodes)
        self.new_attrs = attributes

    def inverse(self):
        return UpdateNodes(self.tracks, self.nodes, attributes=self.old_attrs)

    def apply(self):
        self.tracks.set_node_attributes(self.nodes, self.new_attrs)


class AddEdges(TracksAction):
    def __init__(self, tracks: Tracks, edges, attributes):
        super().__init__(tracks)
        self.edges = edges
        self.attributes = attributes

    def inverse(self):
        return DeleteEdges(self.tracks, self.edges)

    def is_valid(self, edge):
        return True

    def apply(self):
        """
        Steps:
        - for each edge, check if it is valid, then add to graph if so
        """
        for idx, edge in enumerate(self.edges):
            if self.is_valid(edge):
                attrs = {attr: val[idx] for attr, val in self.attributes.items()}
                self.tracks.graph.add_edge(edge[0], edge[1], **attrs)


class UpdateTrackID(TracksAction):
    def __init__(self, tracks: Tracks, start_node, track_id):
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
        return UpdateTrackID(self.tracks, self.start_node, self.old_track_id)

    def apply(self):
        """Assign a new track id to the track starting with start_node.
        Will also update the self.tracks.segmentation array and seg_id on the
        self.tracks.graph if a segmentation exists.
        """
        old_track_id = self.tracks.get_track_id(self.start_node)
        curr_node = self.start_node
        while self.tracks.get_track_id(curr_node) == old_track_id:
            print(f"updating node {curr_node} to track_id {self.new_track_id}")
            # update the track id
            self.tracks.graph.nodes[curr_node][NodeAttr.TRACK_ID.value] = (
                self.new_track_id
            )
            self.tracks.node_id_to_track_id[curr_node] = self.new_track_id
            if self.tracks.segmentation is not None:
                time = self.tracks.get_time(curr_node)
                # update the segmentation to match the new track id
                self.tracks.update_segmentation(time, old_track_id, self.new_track_id)
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
    def __init__(self, tracks: Tracks, edges):
        super().__init__(tracks)
        self.edges = edges
        self.attributes = tracks.get_edge_attributes(self.edges)

    def inverse(self):
        return AddEdges(self.tracks, self.edges, self.attributes)

    def apply(self):
        """Steps:
        - Remove the edges from the graph
        """
        self.tracks.graph.remove_edges_from(self.edges)


class UpdateEdges(TracksAction):
    def __init__(self, tracks: Tracks, edges, attributes):
        super().__init__(UpdateEdges.__name__, tracks)
        self.edges = edges
        self.old_attrs = tracks.get_edge_attributes(self.edges)
        self.new_attrs = attributes

    def inverse(self):
        return UpdateEdges(self.tracks, self.edges, self.old_attrs)

    def apply(self):
        """Steps:
        - update the attributes of all edges to the new values
        """
        self.tracks.set_edge_attributes(self.edges, self.new_attrs)
