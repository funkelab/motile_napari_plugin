import logging
import time
from collections.abc import Callable

import networkx as nx
import numpy as np
from motile import Solver, TrackGraph
from motile.constraints import MaxChildren, MaxParents
from motile.costs import Appear, EdgeDistance, EdgeSelection, Split
from motile_toolbox.candidate_graph import (
    EdgeAttr,
    NodeAttr,
    get_candidate_graph,
    get_candidate_graph_from_points_list,
    graph_to_nx,
)
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids

from .solver_params import SolverParams

logger = logging.getLogger(__name__)


def solve(
    solver_params: SolverParams,
    input_data: np.ndarray,
    on_solver_update: Callable | None = None,
    scale: list | None = None,
) -> nx.DiGraph:
    """Get a tracking solution for the given segmentation and parameters.

    Constructs a candidate graph from the segmentation, a solver from
    the parameters, and then runs solving and returns a networkx graph
    with the solution. Most of this functionality is implemented in the
    motile toolbox.

    Args:
        solver_params (SolverParams): The solver parameters to use when
            initializing the solver
        input_data (np.ndarray): The input segmentation or points list to run
            tracking on. If 2D, assumed to be a list of points, otherwise a
            segmentation.
        on_solver_update (Callable, optional): A function that is called
            whenever the motile solver emits an event. The function should take
            a dictionary of event data, and can be used to track progress of
            the solver. Defaults to None.

    Returns:
        nx.DiGraph: A solution graph where the ids of the nodes correspond to
            the time and ids of the passed in segmentation labels. See the
            motile_toolbox for exact implementation details.
    """
    if input_data.ndim == 2:
        cand_graph = get_candidate_graph_from_points_list(
            input_data, solver_params.max_edge_distance, scale=scale
        )
    else:
        cand_graph, _ = get_candidate_graph(
            input_data,
            solver_params.max_edge_distance,
            iou=solver_params.iou_cost is not None,
            scale=scale,
        )
    logger.debug("Cand graph has %d nodes", cand_graph.number_of_nodes())
    solver = construct_solver(cand_graph, solver_params)
    start_time = time.time()
    solution = solver.solve(verbose=False, on_event=on_solver_update)
    logger.info("Solution took %.2f seconds", time.time() - start_time)

    solution_graph = solver.get_selected_subgraph(solution=solution)
    solution_nx_graph = graph_to_nx(solution_graph)
    solution_nx_graph, _ = assign_tracklet_ids(solution_nx_graph)
    return solution_nx_graph


def construct_solver(cand_graph: nx.DiGraph, solver_params: SolverParams) -> Solver:
    """Construct a motile solver with the parameters specified in the solver
    params object.

    Args:
        cand_graph (nx.DiGraph): The candidate graph to use in the solver
        solver_params (SolverParams): The costs and constraints to use in
            the solver

    Returns:
        Solver: A motile solver with the specified graph, costs, and
            constraints.
    """
    solver = Solver(TrackGraph(cand_graph, frame_attribute=NodeAttr.TIME.value))
    solver.add_constraint(MaxChildren(solver_params.max_children))
    solver.add_constraint(MaxParents(1))

    # Using EdgeDistance instead of EdgeSelection for the constant cost because
    # the attribute is not optional for EdgeSelection (yet)
    if solver_params.edge_selection_cost is not None:
        solver.add_cost(
            EdgeDistance(
                weight=0,
                position_attribute=NodeAttr.POS.value,
                constant=solver_params.edge_selection_cost,
            ),
            name="edge_const",
        )
    if solver_params.appear_cost is not None:
        solver.add_cost(Appear(solver_params.appear_cost))
    if solver_params.division_cost is not None:
        solver.add_cost(Split(constant=solver_params.division_cost))

    if solver_params.distance_cost is not None:
        solver.add_cost(
            EdgeDistance(
                position_attribute=NodeAttr.POS.value,
                weight=solver_params.distance_cost,
            ),
            name="distance",
        )
    if solver_params.iou_cost is not None:
        solver.add_cost(
            EdgeSelection(
                weight=solver_params.iou_cost,
                attribute=EdgeAttr.IOU.value,
            ),
            name="iou",
        )
    return solver
