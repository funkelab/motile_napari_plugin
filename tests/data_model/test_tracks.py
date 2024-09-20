import numpy as np
from motile_plugin.data_model import Tracks
from motile_plugin.data_model.tracks import nx_graph_to_spatial
from motile_toolbox.candidate_graph import NodeAttr
from numpy.testing import assert_array_almost_equal


def test_nx_to_spatial_graph(graph_2d):
    spatial_graph, node_ids_map = nx_graph_to_spatial(
        graph_2d, time_attr=NodeAttr.TIME.value, pos_attr=NodeAttr.POS.value, ndims=3
    )

    for node in graph_2d.nodes():
        sg_id = node_ids_map[node]
        expected_position = np.array(
            [
                graph_2d.nodes[node][NodeAttr.TIME.value],
                *graph_2d.nodes[node][NodeAttr.POS.value],
            ],
            dtype="double",
        )
        assert_array_almost_equal(
            spatial_graph.node_attrs[sg_id].position, expected_position
        )
        expected_trackid = np.array(
            graph_2d.nodes[node][NodeAttr.TRACK_ID.value], dtype="uint16"
        )
        assert_array_almost_equal(
            spatial_graph.node_attrs[sg_id].track_id, expected_trackid
        )
    expected_nodes = np.array([0, 1, 2], dtype=np.uint64)
    expected_edges = np.array([[0, 1], [0, 2]], dtype=np.uint64)
    whole_roi = np.array([[0, 0, 0], [100, 100, 100]], dtype="double")
    actual_nodes, actual_edges = spatial_graph.query_in_roi(
        whole_roi, edge_inclusion="incident"
    )
    assert_array_almost_equal(actual_nodes, expected_nodes)
    assert_array_almost_equal(actual_edges, expected_edges)

    # test multiple position attrs
    pos_attr = ("y", "x")
    for node in graph_2d.nodes():
        pos = graph_2d.nodes[node][NodeAttr.POS.value]
        y, x = pos
        del graph_2d.nodes[node][NodeAttr.POS.value]
        graph_2d.nodes[node]["y"] = y
        graph_2d.nodes[node]["x"] = x

    spatial_graph, node_ids_map = nx_graph_to_spatial(
        graph_2d, time_attr=NodeAttr.TIME.value, pos_attr=pos_attr, ndims=3
    )

    for node in graph_2d.nodes():
        sg_id = node_ids_map[node]
        expected_position = np.array(
            [
                graph_2d.nodes[node][NodeAttr.TIME.value],
                graph_2d.nodes[node]["y"],
                graph_2d.nodes[node]["x"],
            ],
            dtype="double",
        )
        assert_array_almost_equal(
            spatial_graph.node_attrs[sg_id].position, expected_position
        )
        expected_trackid = np.array(
            graph_2d.nodes[node][NodeAttr.TRACK_ID.value], dtype="uint16"
        )
        assert_array_almost_equal(
            spatial_graph.node_attrs[sg_id].track_id, expected_trackid
        )
    expected_nodes = np.array([0, 1, 2], dtype=np.uint64)
    expected_edges = np.array([[0, 1], [0, 2]], dtype=np.uint64)
    whole_roi = np.array([[0, 0, 0], [100, 100, 100]], dtype="double")
    actual_nodes, actual_edges = spatial_graph.query_in_roi(
        whole_roi, edge_inclusion="incident"
    )
    assert_array_almost_equal(actual_nodes, expected_nodes)
    assert_array_almost_equal(actual_edges, expected_edges)


def test_tracks(graph_2d):
    spatial_graph, node_ids_map = nx_graph_to_spatial(
        graph_2d, NodeAttr.TIME.value, NodeAttr.POS.value, ndims=3
    )
    tracks = Tracks(graph=spatial_graph)

    assert_array_almost_equal(
        tracks.get_location(node_ids_map["0_1"]), np.array([50, 50], dtype="double")
    )
    assert tracks.get_time(node_ids_map["0_1"]) == 0
    assert_array_almost_equal(
        tracks.get_location(node_ids_map["0_1"], incl_time=True),
        np.array([0, 50, 50], dtype="double"),
    )
    assert tracks.get_area(node_ids_map["0_1"]) is None
    assert tracks.get_track_id(node_ids_map["0_1"]) == 3
    # with pytest.raises(KeyError):
    #     tracks.get_location(10)
