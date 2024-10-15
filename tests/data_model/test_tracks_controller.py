import numpy as np
from motile_plugin.data_model.solution_tracks import SolutionTracks
from motile_plugin.data_model.tracks_controller import TracksController
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr


def test__add_nodes_no_seg(graph_2d):
    # add without segmentation
    tracks = SolutionTracks(graph_2d, ndim=3)
    controller = TracksController(tracks)

    num_edges = tracks.graph.number_of_edges()

    # start a new track
    attrs = {
        NodeAttr.TIME.value: [0],
        NodeAttr.POS.value: np.array([[1, 3]]),
        NodeAttr.TRACK_ID.value: [6],
    }

    action, node_ids = controller._add_nodes(attrs)

    node = node_ids[0]
    assert tracks.get_position(node) == [1, 3]
    assert tracks.get_track_id(node) == 6
    assert tracks.get_seg_id(node) is None

    assert tracks.graph.number_of_edges() == num_edges  # no edges added

    # add node to end of existing track
    attrs = {
        NodeAttr.TIME.value: [2],
        NodeAttr.POS.value: np.array([[1, 3]]),
        NodeAttr.TRACK_ID.value: [2],
    }

    action, node_ids = controller._add_nodes(attrs)

    node = node_ids[0]
    assert tracks.get_position(node) == [1, 3]
    assert tracks.get_track_id(node) == 2
    assert tracks.get_seg_id(node) is None

    assert tracks.graph.has_edge("1_2", node)

    # add node to middle of existing track
    attrs = {
        NodeAttr.TIME.value: [3],
        NodeAttr.POS.value: np.array([[1, 3]]),
        NodeAttr.TRACK_ID.value: [3],
    }

    action, node_ids = controller._add_nodes(attrs)

    node = node_ids[0]
    assert tracks.get_position(node) == [1, 3]
    assert tracks.get_track_id(node) == 3
    assert tracks.get_seg_id(node) is None

    assert tracks.graph.has_edge(2, node)
    assert tracks.graph.has_edge(node, 4)
    assert not tracks.graph.has_edge(2, 4)


def test__add_nodes_with_seg(graph_2d, segmentation_2d):
    # add with segmentation
    tracks = SolutionTracks(graph_2d, segmentation=segmentation_2d)
    controller = TracksController(tracks)

    num_edges = tracks.graph.number_of_edges()

    new_seg = segmentation_2d.copy()
    time = 0
    seg_id = 6
    new_seg[time, 0, 90:100, 0:4] = seg_id
    expected_center = [94.5, 1.5]
    # start a new track
    attrs = {
        NodeAttr.TIME.value: [time],
        NodeAttr.TRACK_ID.value: [seg_id],
        NodeAttr.SEG_ID.value: [seg_id],
    }

    loc_pix = np.where(new_seg[time] == seg_id)
    time_pix = np.ones_like(loc_pix[0]) * time
    pixels = [(time_pix, *loc_pix)]  # TODO: get time from pixels?

    action, node_ids = controller._add_nodes(attrs, pixels=pixels)

    node = node_ids[0]
    assert tracks.get_time(node) == 0
    assert tracks.get_position(node) == expected_center
    assert tracks.get_track_id(node) == 6
    assert tracks.get_seg_id(node) == 6
    assert np.sum(tracks.segmentation != new_seg) == 0

    assert tracks.graph.number_of_edges() == num_edges  # no edges added

    # add node to end of existing track
    time = 2
    seg_id = 2
    new_seg[time, 0, 0:10, 0:4] = seg_id
    expected_center = [4.5, 1.5]
    # start a new track
    attrs = {
        NodeAttr.TIME.value: [time],
        NodeAttr.TRACK_ID.value: [seg_id],
        NodeAttr.SEG_ID.value: [seg_id],
    }

    loc_pix = np.where(new_seg[time] == seg_id)
    time_pix = np.ones_like(loc_pix[0]) * time
    pixels = [(time_pix, *loc_pix)]

    action, node_ids = controller._add_nodes(attrs, pixels)

    node = node_ids[0]
    assert tracks.get_position(node) == expected_center
    assert tracks.get_track_id(node) == 2
    assert tracks.get_seg_id(node) == 2
    assert np.sum(tracks.segmentation != new_seg) == 0

    assert tracks.graph.has_edge("1_2", node)

    # add node to middle of existing track
    time = 3
    seg_id = 3
    new_seg[time, 0, 0:10, 0:4] = seg_id
    expected_center = [4.5, 1.5]
    attrs = {
        NodeAttr.TIME.value: [time],
        NodeAttr.TRACK_ID.value: [seg_id],
        NodeAttr.SEG_ID.value: [seg_id],
    }

    loc_pix = np.where(new_seg[time] == seg_id)
    time_pix = np.ones_like(loc_pix[0]) * time
    pixels = [(time_pix, *loc_pix)]

    action, node_ids = controller._add_nodes(attrs, pixels=pixels)

    node = node_ids[0]
    assert tracks.get_seg_id(node) == 3
    assert tracks.get_position(node) == expected_center
    assert tracks.get_track_id(node) == 3
    assert np.sum(tracks.segmentation != new_seg) == 0

    assert tracks.graph.has_edge(2, node)
    assert tracks.graph.has_edge(node, 4)
    assert not tracks.graph.has_edge(2, 4)


def test__delete_nodes_no_seg(graph_2d):
    tracks = SolutionTracks(graph_2d, ndim=3)
    controller = TracksController(tracks)
    num_edges = tracks.graph.number_of_edges()

    # delete unconnected node
    node = 5
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert tracks.graph.number_of_edges() == num_edges
    action.inverse()

    # delete end node
    node = 4
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert not tracks.graph.has_edge(3, node)
    action.inverse()

    # delete continuation node
    node = 2
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert not tracks.graph.has_edge("1_3", node)
    assert not tracks.graph.has_edge(node, 4)
    assert tracks.graph.has_edge("1_3", 4)
    assert tracks.get_track_id(4) == 3
    action.inverse()

    # delete div parent
    node = "0_1"
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert not tracks.graph.has_edge(node, "1_2")
    assert not tracks.graph.has_edge(node, "1_3")
    action.inverse()

    # delete div child
    node = "1_2"
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert tracks.get_track_id("1_3") == 1  # update track id for other child
    assert tracks.get_track_id(4) == 1  # update track id for other child


def test__delete_nodes_with_seg(graph_2d, segmentation_2d):
    tracks = SolutionTracks(graph_2d, segmentation=segmentation_2d)
    controller = TracksController(tracks)
    num_edges = tracks.graph.number_of_edges()

    # delete unconnected node
    node = 5
    track_id = 5
    time = 4
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert track_id not in np.unique(tracks.segmentation[time])
    assert tracks.graph.number_of_edges() == num_edges
    action.inverse()

    # delete end node
    node = 4
    track_id = 3
    time = 4
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert track_id not in np.unique(tracks.segmentation[time])
    assert not tracks.graph.has_edge(3, node)
    action.inverse()

    # delete continuation node
    node = 2
    track_id = 3
    time = 2
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert track_id not in np.unique(tracks.segmentation[time])
    assert not tracks.graph.has_edge("1_3", node)
    assert not tracks.graph.has_edge(node, 4)
    assert tracks.graph.has_edge("1_3", 4)
    assert tracks.get_track_id(4) == 3
    action.inverse()

    # delete div parent
    node = "0_1"
    track_id = 1
    time = 0
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert track_id not in np.unique(tracks.segmentation[time])
    assert not tracks.graph.has_edge(node, "1_2")
    assert not tracks.graph.has_edge(node, "1_3")
    action.inverse()

    # delete div child
    node = "1_2"
    track_id = 2
    time = 1
    action = controller._delete_nodes([node])
    assert not tracks.graph.has_node(node)
    assert track_id not in np.unique(tracks.segmentation[time])
    assert tracks.get_track_id("1_3") == 1  # update track id for other child
    assert tracks.get_track_id(4) == 1  # update track id for other child


def test__add_remove_edges_no_seg(graph_2d):
    tracks = SolutionTracks(graph_2d, ndim=3)
    controller = TracksController(tracks)
    num_edges = tracks.graph.number_of_edges()

    # delete continuation edge
    edge = ("1_3", 2)
    track_id = 3
    controller._delete_edges([edge])
    assert not tracks.graph.has_edge(*edge)
    assert tracks.get_track_id(edge[1]) != track_id  # relabeled the rest of the track
    assert tracks.graph.number_of_edges() == num_edges - 1

    # add back in continuation edge
    controller._add_edges([edge])
    assert tracks.graph.has_edge(*edge)
    assert tracks.get_track_id(edge[1]) == track_id  # track id was changed back
    assert tracks.graph.number_of_edges() == num_edges

    # delete division edge
    edge = ("0_1", "1_3")
    track_id = 3
    controller._delete_edges([edge])
    assert not tracks.graph.has_edge(*edge)
    assert tracks.get_track_id(edge[1]) == track_id  # dont relabel after removal
    assert tracks.get_track_id("1_2") == 1  # but do relabel the sibling
    assert tracks.graph.number_of_edges() == num_edges - 1

    # add back in division edge
    edge = ("0_1", "1_3")
    track_id = 3
    controller._add_edges([edge])
    assert tracks.graph.has_edge(*edge)
    assert tracks.get_track_id(edge[1]) == track_id  # dont relabel after removal
    assert (
        tracks.get_track_id("1_2") != 1
    )  # give sibling new id again (not necessarily 2)
    assert tracks.graph.number_of_edges() == num_edges
