import networkx as nx
import numpy as np
import pytest
from motile_plugin.data_model import Tracks
from motile_toolbox.candidate_graph import NodeAttr


def test_create_tracks(graph_3d, segmentation_3d):
    # create empty tracks
    tracks = Tracks(graph=nx.DiGraph(), ndim=3)
    with pytest.raises(KeyError):
        tracks.get_positions([1])

    # create tracks with graph only
    tracks = Tracks(graph=graph_3d, ndim=4)
    assert tracks.get_positions(["0_1"]).tolist() == [[50, 50, 50]]
    assert tracks.get_time("0_1") == 0
    with pytest.raises(KeyError):
        tracks.get_positions(["0"])

    # create track with graph and seg
    tracks = Tracks(graph=graph_3d, segmentation=segmentation_3d)
    assert tracks.get_positions(["0_1"]).tolist() == [[50, 50, 50]]
    assert tracks.get_time("0_1") == 0
    assert tracks.get_positions(["0_1"], incl_time=True).tolist() == [[0, 50, 50, 50]]
    tracks.set_time("0_1", 1)
    assert tracks.get_positions(["0_1"], incl_time=True).tolist() == [[1, 50, 50, 50]]
    assert tracks.get_seg_id("0_1") == 1
    assert tracks.get_node(seg_id=1, time=1) == "0_1"

    with pytest.raises(KeyError):  # raises error at construction if time is wrong
        tracks_wrong_attr = Tracks(
            graph=graph_3d, segmentation=segmentation_3d, time_attr="test"
        )

    tracks_wrong_attr = Tracks(graph=graph_3d, pos_attr="test", ndim=3)
    with pytest.raises(KeyError):
        tracks_wrong_attr.get_positions(["0_1"])

    # test multiple position attrs
    pos_attr = ("z", "y", "x")
    for node in graph_3d.nodes():
        pos = graph_3d.nodes[node][NodeAttr.POS.value]
        z, y, x = pos
        del graph_3d.nodes[node][NodeAttr.POS.value]
        graph_3d.nodes[node]["z"] = z
        graph_3d.nodes[node]["y"] = y
        graph_3d.nodes[node]["x"] = x

    tracks = Tracks(graph=graph_3d, pos_attr=pos_attr, ndim=4)
    assert tracks.get_positions(["0_1"]).tolist() == [[50, 50, 50]]
    tracks.set_position("0_1", [55, 56, 57])
    assert tracks.get_position("0_1") == [55, 56, 57]

    tracks.set_position("0_1", [1, 50, 50, 50], incl_time=True)
    assert tracks.get_time("0_1") == 1


def test_add_remove_nodes(graph_2d, segmentation_2d):
    # create empty tracks
    tracks = Tracks(graph=nx.DiGraph(), ndim=3)
    with pytest.raises(KeyError):
        tracks.get_positions([1])
    # add a node
    tracks.add_node(1, time=0, position=[0, 0, 0])
    assert tracks.get_positions([1]).tolist() == [[0, 0, 0]]
    assert tracks.get_time(1) == 0
    # remove the node
    tracks.remove_node(1)
    with pytest.raises(KeyError):
        tracks.get_positions([1])

    # add a position-less node
    with pytest.raises(ValueError):
        tracks.add_node(1, time=10)

    # create tracks with segmentation
    tracks = Tracks(graph=graph_2d, segmentation=segmentation_2d, scale=[1, 2, 1])

    # removing a node removes it from the seg_time mapping
    node = "1_3"
    assert tracks.get_node(seg_id=3, time=1) == node
    tracks.remove_node(node)
    assert tracks.get_node(3, 1) is None
    with pytest.raises(KeyError):
        tracks.get_position(node)

    with pytest.raises(KeyError):
        tracks.get_positions([node])
    # adding a node with a given seg_id infers position from segmentation
    tracks.add_node(node, time=1, seg_id=3)
    assert tracks.get_node(seg_id=3, time=1) == node
    assert tracks.get_area(node) == 697 * 2


def test_add_remove_edges(graph_2d, segmentation_2d):
    # create empty tracks
    tracks = Tracks(graph=nx.DiGraph(), ndim=3)
    with pytest.raises(KeyError):
        tracks.get_positions([1])
    # add a node
    tracks.add_node(1, time=0, position=[0, 0, 0])
    assert tracks.get_positions([1]).tolist() == [[0, 0, 0]]
    assert tracks.get_time(1) == 0
    # remove the node
    tracks.remove_node(1)
    with pytest.raises(KeyError):
        tracks.get_positions([1])

    # add an edge
    with pytest.raises(KeyError):
        tracks.add_edge((1, 2))

    tracks.add_node(1, time=0, position=[0, 0, 0])
    tracks.add_node(2, time=1, position=[1, 1, 1])
    tracks.add_edge((1, 2))
    assert tracks.graph.number_of_edges() == 1

    # create track with graph and seg
    tracks = Tracks(graph=graph_2d, segmentation=segmentation_2d)
    num_edges = tracks.graph.number_of_edges()

    edge = ("0_1", "1_3")
    iou = tracks.get_iou(edge)
    tracks.remove_edge(edge)
    assert tracks.graph.number_of_edges() == num_edges - 1
    tracks.add_edge(edge)
    assert tracks.graph.number_of_edges() == num_edges
    assert pytest.approx(tracks.get_iou(edge), abs=0.01) == iou

    edges = [("0_1", "1_3"), ("0_1", "1_2")]
    tracks.remove_edges(edges)
    assert tracks.graph.number_of_edges() == num_edges - 2

    with pytest.raises(KeyError):
        tracks.remove_edge((1, 2))

    with pytest.raises(KeyError):
        tracks.remove_edges([("0_1", "1_3"), (1, 2)])

    # with pytest.raises(ValueError):
    #     # TODO: what happens if you add a duplicate edge? remove a nonexisting edge?
    # tracks.add_edge(edge)


def test_pixels_and_seg_id(graph_3d, segmentation_3d):
    # create track with graph and seg
    tracks = Tracks(graph=graph_3d, segmentation=segmentation_3d)

    # changing a segmentation id changes it in the mapping
    assert tracks.get_node(1, 0) == "0_1"
    pix = tracks.get_pixels(["0_1"])
    print(pix)
    new_seg_id = 10
    tracks.set_pixels(pix, [new_seg_id])
    tracks.set_seg_id("0_1", new_seg_id)
    assert tracks.get_node(1, 0) is None
    assert tracks.get_node(new_seg_id, 0) == "0_1"

    with pytest.raises(KeyError):
        tracks.get_positions(["0"])


def test_update_segmentations(graph_2d, segmentation_2d):
    tracks = Tracks(graph_2d.copy(), segmentation=segmentation_2d.copy())

    # remove pixels from a segmentation
    nodes = ["0_1"]
    edge = ("0_1", "1_3")
    current_pix = tracks.get_pixels(nodes)
    areas = tracks.get_areas(nodes)
    iou = tracks.get_iou(edge)
    # get the first 5 pixels of each segmentation
    pix_to_remove = [
        tuple(pix[dim][0:5] for dim in range(segmentation_2d.ndim))
        for pix in current_pix
    ]
    tracks.update_segmentations(nodes, pix_to_remove, added=False)

    # there are 5 different pixels for each node
    assert np.sum(segmentation_2d != tracks.segmentation) == len(nodes) * 5

    # the areas have updated
    for node, area in zip(nodes, areas, strict=False):
        assert tracks.get_area(node) == area - 5

    # the edge IOUs have updated
    assert tracks.get_iou(edge) < iou

    # add pixels back to the segmentation
    tracks.update_segmentations(nodes, pix_to_remove, added=True)
    assert np.sum(segmentation_2d != tracks.segmentation) == 0

    # the areas have updated
    for node, area in zip(nodes, areas, strict=False):
        assert tracks.get_area(node) == area

    # the edge IOUs have updated
    assert tracks.get_iou(edge) == pytest.approx(iou, abs=0.01)
