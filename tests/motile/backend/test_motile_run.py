import networkx as nx
import numpy as np
from motile_plugin.motile.backend import MotileRun, SolverParams


def test_save_load(tmp_path, graph_2d):
    segmentation = np.zeros((10, 1, 10, 10))
    for i in range(10):
        segmentation[i][:, 0:5, 0:5] = i

    run_name = "test"
    scale = [1.0, 2.0, 3.0]
    run = MotileRun(
        graph=graph_2d,
        segmentation=segmentation,
        run_name=run_name,
        solver_params=SolverParams(),
        scale=scale,
    )
    path = run.save(tmp_path)
    newrun = MotileRun.load(path)
    assert nx.utils.graphs_equal(run.graph, newrun.graph)
    np.testing.assert_array_equal(run.segmentation, newrun.segmentation)
    assert run.run_name == newrun.run_name
    assert run.time.replace(microsecond=0) == newrun.time
    assert run.gaps == newrun.gaps
    assert run.scale == newrun.scale
    assert run.solver_params == newrun.solver_params
