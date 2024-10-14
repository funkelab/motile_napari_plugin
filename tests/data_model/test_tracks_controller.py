import numpy as np
from motile_plugin.data_model.solution_tracks import SolutionTracks
from motile_plugin.data_model.tracks_controller import TracksController
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr


def test__add_nodes_no_seg(graph_2d):
    graph_2d.add_node(4, pos=[0, 2], time=4, track_id=3)
    graph_2d.add_edge("1_3", 4)

    # add without segmentation
    tracks = SolutionTracks(graph_2d, ndim=3)
    controller = TracksController(tracks)

    num_edges = tracks.graph.number_of_edges()

    # start a new track
    attrs = {
        NodeAttr.TIME.value: [0],
        NodeAttr.POS.value: np.array([[1, 3]]),
        NodeAttr.TRACK_ID.value: [5],
    }

    action, node_ids = controller._add_nodes(attrs)
    action.apply()

    node = node_ids[0]
    assert tracks.get_position(node) == [1, 3]
    assert tracks.get_track_id(node) == 5
    assert tracks.get_seg_id(node) is None

    assert tracks.graph.number_of_edges() == num_edges  # no edges added

    # add node to end of existing track
    attrs = {
        NodeAttr.TIME.value: [2],
        NodeAttr.POS.value: np.array([[1, 3]]),
        NodeAttr.TRACK_ID.value: [2],
    }

    action, node_ids = controller._add_nodes(attrs)
    action.apply()

    node = node_ids[0]
    assert tracks.get_position(node) == [1, 3]
    assert tracks.get_track_id(node) == 2
    assert tracks.get_seg_id(node) is None

    assert tracks.graph.has_edge("1_2", node)

    # add node to middle of existing track
    attrs = {
        NodeAttr.TIME.value: [2],
        NodeAttr.POS.value: np.array([[1, 3]]),
        NodeAttr.TRACK_ID.value: [3],
    }

    action, node_ids = controller._add_nodes(attrs)
    action.apply()

    node = node_ids[0]
    assert tracks.get_position(node) == [1, 3]
    assert tracks.get_track_id(node) == 3
    assert tracks.get_seg_id(node) is None

    assert tracks.graph.has_edge("1_3", node)
    assert tracks.graph.has_edge(node, 4)
    assert not tracks.graph.has_edge("1_3", 4)


def test__add_nodes_with_seg(graph_2d, segmentation_2d):
    graph_2d.add_node(4, pos=[0, 2], time=4, track_id=3)
    graph_2d.add_edge("1_3", 4)

    segmentation_2d[4, 0, 0, 0:4] = 3
    # add with segmentation
    tracks = SolutionTracks(graph_2d, segmentation=segmentation_2d)
    controller = TracksController(tracks)

    num_edges = tracks.graph.number_of_edges()

    new_seg = segmentation_2d.copy()
    time = 0
    seg_id = 5
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
    pixels = [(time_pix, *loc_pix)]  # TODO: get time from pixels?

    action, node_ids = controller._add_nodes(attrs, pixels=pixels)
    action.apply()

    node = node_ids[0]
    assert tracks.get_time(node) == 0
    assert tracks.get_position(node) == expected_center
    assert tracks.get_track_id(node) == 5
    assert tracks.get_seg_id(node) == 5
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
    action.apply()

    node = node_ids[0]
    assert tracks.get_position(node) == expected_center
    assert tracks.get_track_id(node) == 2
    assert tracks.get_seg_id(node) == 2
    assert np.sum(tracks.segmentation != new_seg) == 0

    assert tracks.graph.has_edge("1_2", node)

    # add node to middle of existing track
    time = 2
    seg_id = 3
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

    action, node_ids = controller._add_nodes(attrs, pixels=pixels)
    action.apply()

    node = node_ids[0]
    assert tracks.get_seg_id(node) == 3
    assert tracks.get_position(node) == expected_center
    assert tracks.get_track_id(node) == 3
    assert np.sum(tracks.segmentation != new_seg) == 0

    assert tracks.graph.has_edge("1_3", node)
    assert tracks.graph.has_edge(node, 4)
    assert not tracks.graph.has_edge("1_3", 4)
