import networkx as nx
import numpy as np
from motile_plugin.data_model import Tracks
from motile_plugin.data_model.actions import (
    AddEdges,
    AddNodes,
    UpdateEdges,
    UpdateNodes,
    UpdateTrackID,
)
from motile_toolbox.candidate_graph.graph_attributes import EdgeAttr, NodeAttr
from numpy.testing import assert_array_almost_equal
from skimage.measure import regionprops


def test_add_delete_nodes(segmentation_2d, graph_2d):
    empty_graph = nx.DiGraph()
    empty_seg = np.zeros_like(segmentation_2d)
    tracks = Tracks(empty_graph, segmentation=empty_seg)
    nodes = list(graph_2d.nodes())

    attrs = {}
    attrs[NodeAttr.TIME.value] = [
        graph_2d.nodes[node][NodeAttr.TIME.value] for node in nodes
    ]
    attrs[NodeAttr.POS.value] = [
        graph_2d.nodes[node][NodeAttr.POS.value] for node in nodes
    ]
    attrs[NodeAttr.TRACK_ID.value] = [
        graph_2d.nodes[node][NodeAttr.TRACK_ID.value] for node in nodes
    ]
    attrs[NodeAttr.SEG_ID.value] = [
        graph_2d.nodes[node][NodeAttr.SEG_ID.value] for node in nodes
    ]
    attrs[NodeAttr.AREA.value] = [
        graph_2d.nodes[node].get(NodeAttr.AREA.value, None) for node in nodes
    ]

    pixels = [
        np.nonzero(segmentation_2d == track_id)
        for track_id in attrs[NodeAttr.TRACK_ID.value]
    ]
    add_nodes = AddNodes(tracks, nodes, attributes=attrs, pixels=pixels)
    add_nodes.apply()

    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    for node, data in tracks.graph.nodes(data=True):
        graph_2d_data = graph_2d.nodes[node]
        if NodeAttr.AREA.value not in graph_2d_data:
            graph_2d_data[NodeAttr.AREA.value] = None
        assert data == graph_2d_data
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    del_nodes = add_nodes.inverse()
    del_nodes.apply()
    assert set(tracks.graph.nodes()) == set(empty_graph.nodes())
    assert_array_almost_equal(tracks.segmentation, empty_seg)

    re_add = del_nodes.inverse()
    re_add.apply()

    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    for node, data in tracks.graph.nodes(data=True):
        graph_2d_data = graph_2d.nodes[node]
        if NodeAttr.AREA.value not in graph_2d_data:
            graph_2d_data[NodeAttr.AREA.value] = None
        assert data == graph_2d_data
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)


def test_update_nodes(segmentation_2d, graph_2d):
    tracks = Tracks(graph_2d.copy(), segmentation=segmentation_2d.copy())
    nodes = list(graph_2d.nodes())

    # add a couple pixels to the first node
    new_seg = segmentation_2d.copy()
    new_seg[0][0][0] = 1
    nodes = ["0_1"]
    for prop in regionprops(new_seg[0]):
        new_center = prop.centroid
    attrs = {}
    attrs[NodeAttr.TIME.value] = [
        graph_2d.nodes[node][NodeAttr.TIME.value] for node in nodes
    ]
    attrs[NodeAttr.POS.value] = [new_center]
    attrs[NodeAttr.TRACK_ID.value] = [
        graph_2d.nodes[node][NodeAttr.TRACK_ID.value] for node in nodes
    ]
    attrs[NodeAttr.SEG_ID.value] = [
        graph_2d.nodes[node][NodeAttr.SEG_ID.value] for node in nodes
    ]
    attrs[NodeAttr.AREA.value] = [1345]

    pixels = [np.nonzero(segmentation_2d != new_seg)]
    print(pixels)
    action = UpdateNodes(tracks, nodes, attributes=attrs, pixels=pixels, added=True)
    action.apply()

    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    assert tracks.graph.nodes["0_1"][NodeAttr.AREA.value] == 1345
    assert (
        tracks.graph.nodes["0_1"][NodeAttr.POS.value]
        != graph_2d.nodes["0_1"][NodeAttr.POS.value]
    )
    assert_array_almost_equal(tracks.segmentation, new_seg)

    inverse = action.inverse()
    inverse.apply()
    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    for node, data in tracks.graph.nodes(data=True):
        assert data == graph_2d.nodes[node]
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    redo = inverse.inverse()
    redo.apply()

    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    assert tracks.graph.nodes["0_1"][NodeAttr.AREA.value] == 1345
    assert (
        tracks.graph.nodes["0_1"][NodeAttr.POS.value]
        != graph_2d.nodes["0_1"][NodeAttr.POS.value]
    )
    assert_array_almost_equal(tracks.segmentation, new_seg)


def test_add_delete_edges(graph_2d, segmentation_2d):
    node_graph = nx.create_empty_copy(graph_2d, with_data=True)
    tracks = Tracks(node_graph, segmentation_2d)

    edges = [["0_1", "1_2"], ["0_1", "1_3"]]
    attrs = {}
    attrs[EdgeAttr.IOU.value] = [
        graph_2d.edges[edge][EdgeAttr.IOU.value] for edge in edges
    ]

    action = AddEdges(tracks, edges, attrs)
    action.apply()
    # TODO: What if adding an edge that already exists?
    # TODO: test all the edge cases, invalid operations, etc. for all actions
    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    assert set(tracks.graph.edges()) == set(graph_2d.edges())
    for edge in tracks.graph.edges():
        assert tracks.graph.edges[edge] == graph_2d.edges[edge]
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    inverse = action.inverse()
    inverse.apply()
    assert set(tracks.graph.edges()) == set()
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    redo = inverse.inverse()
    redo.apply()
    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    assert set(tracks.graph.edges()) == set(graph_2d.edges())
    for edge in tracks.graph.edges():
        assert tracks.graph.edges[edge] == graph_2d.edges[edge]
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)


def test_update_edge(graph_2d, segmentation_2d):
    tracks = Tracks(graph_2d.copy(), segmentation_2d)
    edges = [["0_1", "1_2"], ["0_1", "1_3"]]
    attrs = {}
    attrs[EdgeAttr.IOU.value] = [
        graph_2d.edges[edge][EdgeAttr.IOU.value] + 1 for edge in edges
    ]

    action = UpdateEdges(tracks, edges, attrs)
    action.apply()

    assert set(tracks.graph.edges()) == set(graph_2d.edges())
    for edge in tracks.graph.edges():
        assert (
            tracks.graph.edges[edge][EdgeAttr.IOU.value]
            == graph_2d.edges[edge][EdgeAttr.IOU.value] + 1
        )
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    inverse = action.inverse()
    inverse.apply()
    assert set(tracks.graph.edges()) == set(graph_2d.edges())
    for edge in tracks.graph.edges():
        assert (
            tracks.graph.edges[edge][EdgeAttr.IOU.value]
            == graph_2d.edges[edge][EdgeAttr.IOU.value]
        )
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    redo = inverse.inverse()
    redo.apply()

    assert set(tracks.graph.edges()) == set(graph_2d.edges())
    for edge in tracks.graph.edges():
        assert (
            tracks.graph.edges[edge][EdgeAttr.IOU.value]
            == graph_2d.edges[edge][EdgeAttr.IOU.value] + 1
        )
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)


def test_update_track_id_div(graph_2d, segmentation_2d):
    # test with single node track
    tracks = Tracks(graph_2d, segmentation_2d)

    action = UpdateTrackID(tracks, "0_1", 4)
    action.apply()

    expected_seg = segmentation_2d.copy()
    expected_seg[expected_seg == 1] = 4

    assert tracks.graph.nodes["0_1"][NodeAttr.TRACK_ID.value] == 4
    assert tracks.graph.nodes["0_1"][NodeAttr.SEG_ID.value] == 4
    assert_array_almost_equal(tracks.segmentation, expected_seg)

    inverse = action.inverse()
    inverse.apply()

    assert tracks.graph.nodes["0_1"][NodeAttr.TRACK_ID.value] == 1
    assert tracks.graph.nodes["0_1"][NodeAttr.SEG_ID.value] == 1
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    redo = inverse.inverse()
    redo.apply()

    assert tracks.graph.nodes["0_1"][NodeAttr.TRACK_ID.value] == 4
    assert tracks.graph.nodes["0_1"][NodeAttr.SEG_ID.value] == 4
    assert_array_almost_equal(tracks.segmentation, expected_seg)


def test_update_track_id_continue(graph_2d, segmentation_2d):
    # test with two node track
    graph_2d.remove_edge("0_1", "1_3")
    segmentation_2d[segmentation_2d == 2] = 1
    graph_2d.nodes["1_2"][NodeAttr.TRACK_ID.value] = 1
    graph_2d.nodes["1_2"][NodeAttr.SEG_ID.value] = 1
    tracks = Tracks(graph_2d, segmentation_2d)

    # this should now update both 0_1 and 1_2
    action = UpdateTrackID(tracks, "0_1", 5)
    action.apply()

    expected_seg = segmentation_2d.copy()
    expected_seg[expected_seg == 1] = 5
    assert tracks.graph.nodes["0_1"][NodeAttr.TRACK_ID.value] == 5
    assert tracks.graph.nodes["0_1"][NodeAttr.SEG_ID.value] == 5
    assert tracks.graph.nodes["1_2"][NodeAttr.TRACK_ID.value] == 5
    assert tracks.graph.nodes["1_2"][NodeAttr.SEG_ID.value] == 5
    assert_array_almost_equal(tracks.segmentation, expected_seg)

    inverse = action.inverse()
    inverse.apply()

    assert tracks.graph.nodes["0_1"][NodeAttr.TRACK_ID.value] == 1
    assert tracks.graph.nodes["0_1"][NodeAttr.SEG_ID.value] == 1
    assert tracks.graph.nodes["1_2"][NodeAttr.TRACK_ID.value] == 1
    assert tracks.graph.nodes["1_2"][NodeAttr.SEG_ID.value] == 1
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    redo = inverse.inverse()
    redo.apply()

    assert tracks.graph.nodes["0_1"][NodeAttr.TRACK_ID.value] == 5
    assert tracks.graph.nodes["0_1"][NodeAttr.SEG_ID.value] == 5
    assert tracks.graph.nodes["1_2"][NodeAttr.TRACK_ID.value] == 5
    assert tracks.graph.nodes["1_2"][NodeAttr.SEG_ID.value] == 5
    assert_array_almost_equal(tracks.segmentation, expected_seg)
