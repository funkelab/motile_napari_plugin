from motile_tracker.motile.backend import SolverParams, solve


# capsys is a pytest fixture that captures stdout and stderr output streams
def test_solve_2d(segmentation_2d, graph_2d):
    graph_2d.remove_nodes_from([4, 5, 6])
    params = SolverParams()
    params.appear_cost = None
    soln_graph = solve(params, segmentation_2d)
    assert set(soln_graph.nodes) == set(graph_2d.nodes)


def test_solve_3d(segmentation_3d, graph_3d):
    params = SolverParams()
    params.appear_cost = None
    soln_graph = solve(params, segmentation_3d)
    assert set(soln_graph.nodes) == set(graph_3d.nodes)
