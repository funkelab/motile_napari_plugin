import networkx as nx
import numpy as np
from motile_plugin.data_model import Tracks
from motile_plugin.data_model.actions import AddNodes, UpdateNodes
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr
from numpy.testing import assert_array_almost_equal
from skimage.measure import regionprops


def test_add_and_delete_nodes(segmentation_2d, graph_2d):
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
