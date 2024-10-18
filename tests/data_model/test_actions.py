import networkx as nx
import numpy as np
import pytest
from motile_plugin.data_model import Tracks
from motile_plugin.data_model.actions import (
    AddEdges,
    AddNodes,
    UpdateNodeSegs,
)
from motile_toolbox.candidate_graph.graph_attributes import EdgeAttr, NodeAttr
from numpy.testing import assert_array_almost_equal


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
    pixels = [
        np.nonzero(segmentation_2d[time] == track_id)
        for time, track_id in zip(
            attrs[NodeAttr.TIME.value], attrs[NodeAttr.TRACK_ID.value], strict=False
        )
    ]
    pixels = [
        (np.ones_like(pix[0]) * time, *pix)
        for time, pix in zip(attrs[NodeAttr.TIME.value], pixels, strict=False)
    ]
    add_nodes = AddNodes(tracks, nodes, attributes=attrs, pixels=pixels)

    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    for node, data in tracks.graph.nodes(data=True):
        graph_2d_data = graph_2d.nodes[node]
        if NodeAttr.AREA.value not in graph_2d_data:
            graph_2d_data[NodeAttr.AREA.value] = (
                305  # hard coding the case Anniek took out for now
            )
        assert data == graph_2d_data
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    del_nodes = add_nodes.inverse()
    assert set(tracks.graph.nodes()) == set(empty_graph.nodes())
    assert_array_almost_equal(tracks.segmentation, empty_seg)

    del_nodes.inverse()

    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    for node, data in tracks.graph.nodes(data=True):
        graph_2d_data = graph_2d.nodes[node]
        if NodeAttr.AREA.value not in graph_2d_data:
            graph_2d_data[NodeAttr.AREA.value] = None
        assert data == graph_2d_data
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)


def test_update_node_segs(segmentation_2d, graph_2d):
    tracks = Tracks(graph_2d.copy(), segmentation=segmentation_2d.copy())
    nodes = list(graph_2d.nodes())

    # add a couple pixels to the first node
    new_seg = segmentation_2d.copy()
    new_seg[0][0][0] = 1
    nodes = ["0_1"]

    pixels = [np.nonzero(segmentation_2d != new_seg)]
    action = UpdateNodeSegs(tracks, nodes, pixels=pixels, added=True)

    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    assert tracks.graph.nodes["0_1"][NodeAttr.AREA.value] == 1345
    assert (
        tracks.graph.nodes["0_1"][NodeAttr.POS.value]
        != graph_2d.nodes["0_1"][NodeAttr.POS.value]
    )
    assert_array_almost_equal(tracks.segmentation, new_seg)

    inverse = action.inverse()
    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    for node, data in tracks.graph.nodes(data=True):
        assert data == graph_2d.nodes[node]
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    inverse.inverse()

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

    edges = [["0_1", "1_2"], ["0_1", "1_3"], ["1_3", 2], [2, 4]]

    action = AddEdges(tracks, edges)
    # TODO: What if adding an edge that already exists?
    # TODO: test all the edge cases, invalid operations, etc. for all actions
    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    for edge in tracks.graph.edges():
        assert tracks.graph.edges[edge][EdgeAttr.IOU.value] == pytest.approx(
            graph_2d.edges[edge][EdgeAttr.IOU.value], abs=0.01
        )
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    inverse = action.inverse()
    assert set(tracks.graph.edges()) == set()
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)

    inverse.inverse()
    assert set(tracks.graph.nodes()) == set(graph_2d.nodes())
    assert set(tracks.graph.edges()) == set(graph_2d.edges())
    for edge in tracks.graph.edges():
        assert tracks.graph.edges[edge][EdgeAttr.IOU.value] == pytest.approx(
            graph_2d.edges[edge][EdgeAttr.IOU.value], abs=0.01
        )
    assert_array_almost_equal(tracks.segmentation, segmentation_2d)
