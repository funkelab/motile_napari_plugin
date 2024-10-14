import networkx as nx
from motile_plugin.data_model.action_history import ActionHistory
from motile_plugin.data_model.actions import AddEdges, AddNodes, DeleteEdges
from motile_plugin.data_model.tracks import Tracks


def test_action_history():
    history = ActionHistory()
    tracks = Tracks(nx.DiGraph(), ndim=3)
    action1 = AddNodes(
        tracks, nodes=[0, 1], attributes={"time": [0, 1], "pos": [[0, 1], [1, 2]]}
    )
    action2 = AddEdges(tracks, [[0, 1]])
    action3 = DeleteEdges(tracks, [[0, 1]])

    history.append(action1)
    history.append(action2)
    history.append(action3)

    # test undo
    action = history.previous()
    assert action == action3

    action = history.previous()
    assert action == action2

    action = history.previous()
    assert action == action1

    action = history.previous()
    assert action is None

    # test redo
    action = history.next()
    assert action == action1

    action = history.next()
    assert action == action2

    action = history.next()
    assert action == action3

    action = history.next()
    assert action is None

    # test undo and then append
    action = history.previous()
    assert action == action3

    history.append(action1)
    assert len(history.action_list) == 3
    action = history.next()
    assert action is None
    action = history.previous()
    assert action == action1
