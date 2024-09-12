import logging
import time
from typing import Callable

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

from itertools import combinations

from .solver_params import SolverParams

logger = logging.getLogger(__name__)


def solve(
    solver_params: SolverParams,
    input_data: np.ndarray,
    on_solver_update: Callable | None = None,
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
            input_data, solver_params.max_edge_distance
        )
    else:
        cand_graph, _ = get_candidate_graph(
            input_data,
            solver_params.max_edge_distance,
            iou=solver_params.iou_cost is not None,
        )

    

    # 1. add the hyperedges using that function
    cand_graph = add_division_hyperedges(cand_graph)
    
    for (u, v), data in cand_graph.edges.items():
        if isinstance(u, tuple) and len(u) == 1:
            raise ValueError(f"BEFORE CALLING TRACK GRAPH2 Node {u} is a tuple of length 1")
    logger.debug("Cand graph has %d nodes", cand_graph.number_of_nodes())

    # 2. make the motile.TrackGraph here
    track_graph = TrackGraph(cand_graph, frame_attribute="time")
    # 3. add the area attribute with the other function
    add_area_diff_attr(track_graph)
    add_dist_attr(track_graph)

    solver = construct_solver(track_graph, solver_params)
    start_time = time.time()
    solution = solver.solve(verbose=False, on_event=on_solver_update)
    logger.info("Solution took %.2f seconds", time.time() - start_time)

    solution_graph = solver.get_selected_subgraph(solution=solution)
    solution_nx_graph = graph_to_nx(solution_graph)
    solution_nx_graph, _ = assign_tracklet_ids(solution_nx_graph)
    return solution_nx_graph

def add_area_diff_attr(cand_graph: TrackGraph):
    for edge in cand_graph.edges:
        if cand_graph.is_hyperedge(edge):
            us, vs = edge
            u = us[0]  # assume always one "source" node
            v1, v2 = vs  # assume always two "target" nodes
            area_u = cand_graph.nodes[u]["area"]
            area_v = cand_graph.nodes[v1]["area"] + cand_graph.nodes[v2]["area"]
        else:
            u, v = edge
            area_u = cand_graph.nodes[u]["area"]
            area_v = cand_graph.nodes[v]["area"]

        area_diff = np.abs(area_u - area_v)
        cand_graph.edges[edge]["area_diff"] = area_diff

def get_location(graph, node, pos_attr):
    if isinstance(pos_attr, str):
        return np.array(graph.nodes[node][pos_attr])
    else:
        return np.array([graph.nodes[node][dim] for dim in pos_attr])

def add_dist_attr(cand_graph: TrackGraph):
    for edge in cand_graph.edges:
        if cand_graph.is_hyperedge(edge):
            us, vs = edge
            u = us[0]  # assume always one "source" node
            v1, v2 = vs  # assume always two "target" nodes
            pos_u = get_location(cand_graph, u, NodeAttr.POS.value)
            pos_v = (get_location(cand_graph, v1, NodeAttr.POS.value) + get_location(cand_graph, v2, NodeAttr.POS.value)) / 2
        else:
            u, v = edge
            
            pos_u = get_location(cand_graph, u, NodeAttr.POS.value)
            
            pos_v = get_location(cand_graph, v, NodeAttr.POS.value)

        dist = np.linalg.norm(pos_u - pos_v)
        cand_graph.edges[edge]["dist"] = dist


def add_division_hyperedges(candidate_graph: nx.DiGraph) -> nx.DiGraph:
    """Add hyper edges representing specific divisions to the graph

    Args:
        candidate_graph (nx.DiGraph): A candidate graph already populated with
            normal nodes and edges.

    Returns:
        nx.DiGraph: The candidate graph with additional hypernodes for each
            possible division
    """
    nodes_original = list(candidate_graph.nodes)
    for node in nodes_original:
        successors = candidate_graph.successors(node)
        pairs = list(combinations(successors, 2))
        for pair in pairs:
            hypernode = str(node) + "_" + str(pair[0]) + "_" + str(pair[1])
            candidate_graph.add_node(hypernode)
            assert not isinstance(node, tuple)
            candidate_graph.add_edge(
                node,
                hypernode
            )
            assert not isinstance(hypernode, tuple)
            candidate_graph.add_edge(
                hypernode,
                pair[0]
            )
            candidate_graph.add_edge(
                hypernode,
                pair[1]
            )
    return candidate_graph

def construct_solver(
    cand_graph: TrackGraph, solver_params: SolverParams
) -> Solver:
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
    solver = Solver(
        cand_graph
    )
    # 4. Set max children to 1 (because its actuall max out edges)
    solver.add_constraint(MaxChildren(solver_params.max_children)) 
    solver.add_constraint(MaxParents(1))

    # Using EdgeDistance instead of EdgeSelection for the constant cost because
    # the attribute is not optional for EdgeSelection (yet)
    if solver_params.edge_selection_cost is not None:
        solver.add_cost(
            EdgeSelection(
                weight=0,
                attribute="dist",
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
            EdgeSelection(
                attribute="dist",
                weight=solver_params.distance_cost,
            ),
            name="distance",
        )
    # 5. Add an Edge Selection cost with the area diff (hard code the weight)
    weight = 10
    print(f"adding edge selection cost with weight {weight}")
    solver.add_cost(
        EdgeSelection(
            weight= weight,
            attribute="area_diff",
        ),
        name="area",
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
