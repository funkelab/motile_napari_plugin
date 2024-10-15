import networkx as nx
from motile_plugin.data_model.action_history import ActionHistory
from motile_plugin.data_model.actions import AddNodes
from motile_plugin.data_model.tracks import Tracks

# https://github.com/zaboople/klonk/blob/master/TheGURQ.md


def test_action_history():
    history = ActionHistory()
    tracks = Tracks(nx.DiGraph(), ndim=3)
    action1 = AddNodes(
        tracks, nodes=[0, 1], attributes={"time": [0, 1], "pos": [[0, 1], [1, 2]]}
    )

    # empty history has no undo or redo
    assert not history.undo()
    assert not history.redo()

    # add an action to the history
    history.add_new_action(action1)
    # undo the action
    assert history.undo()
    assert tracks.graph.number_of_nodes() == 0
    assert len(history.undo_stack) == 1
    assert len(history.redo_stack) == 1
    assert history.undo_pointer == -1

    # no more actions to undo
    assert not history.undo()

    # redo the action
    assert history.redo()
    assert tracks.graph.number_of_nodes() == 2
    assert len(history.undo_stack) == 1
    assert len(history.redo_stack) == 0
    assert history.undo_pointer == 0

    # no more actions to redo
    assert not history.redo()

    # undo and then add new action
    assert history.undo()
    action2 = AddNodes(tracks, nodes=[10], attributes={"time": [10], "pos": [[0, 1]]})
    history.add_new_action(action2)
    assert tracks.graph.number_of_nodes() == 1
    # there are 3 things on the stack: action1, action1's inverse, and action 2
    assert len(history.undo_stack) == 3
    assert len(history.redo_stack) == 0
    assert history.undo_pointer == 2

    # undo back to after action 1
    assert history.undo()
    assert history.undo()
    assert tracks.graph.number_of_nodes() == 2

    assert len(history.undo_stack) == 3
    assert len(history.redo_stack) == 2
    assert history.undo_pointer == 0
