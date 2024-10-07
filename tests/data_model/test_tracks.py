import pytest
from motile_plugin.data_model import Tracks
from motile_toolbox.candidate_graph import NodeAttr


def test_tracks(graph_3d):
    tracks = Tracks(graph=graph_3d)
    assert tracks.get_location("0_1") == [50, 50, 50]
    assert tracks.get_time("0_1") == 0
    assert tracks.get_location("0_1", incl_time=True) == [0, 50, 50, 50]
    with pytest.raises(KeyError):
        tracks.get_location("0")

    with pytest.raises(KeyError):  # raises error at construction if time is wrong
        tracks_wrong_attr = Tracks(graph=graph_3d, time_attr="test")

    tracks_wrong_attr = Tracks(graph=graph_3d, pos_attr="test")
    with pytest.raises(KeyError):
        tracks_wrong_attr.get_location("0_1")

    # test multiple position attrs
    pos_attr = ("z", "y", "x")
    for node in graph_3d.nodes():
        pos = graph_3d.nodes[node][NodeAttr.POS.value]
        z, y, x = pos
        del graph_3d.nodes[node][NodeAttr.POS.value]
        graph_3d.nodes[node]["z"] = z
        graph_3d.nodes[node]["y"] = y
        graph_3d.nodes[node]["x"] = x

    tracks = Tracks(graph=graph_3d, pos_attr=pos_attr)
    assert tracks.get_location("0_1") == [50, 50, 50]
