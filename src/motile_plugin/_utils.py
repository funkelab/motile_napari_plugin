import math
from pathlib import Path
import numpy as np

from motile import Solver, TrackGraph
from motile.constraints import MaxChildren, MaxParents
from motile.costs import EdgeSelection, Appear, Split
from motile.variables import NodeSelected, EdgeSelected
import networkx as nx
import toml
from tqdm import tqdm
import pprint
import time
from skimage.measure import regionprops
import tifffile
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)-8s %(message)s"
)
logger = logging.getLogger(__name__)


def get_location(node_data, loc_keys=("z", "y", "x")):
    return [node_data[k] for k in loc_keys]


def solve_with_motile(cand_graph, widget):
    motile_cand_graph = TrackGraph(cand_graph)
    solver = Solver(motile_cand_graph)

    solver.add_constraints(MaxChildren(widget.get_max_children()))
    solver.add_constraints(MaxParents(1))

    if widget.get_distance_weight() is not None:
        solver.add_costs(EdgeSelection(widget.get_distance_weight(), attribute="distance", constant=widget.get_distance_offset()))
    if widget.get_appear_cost() is not None:        
        solver.add_costs(Appear(widget.get_appear_cost()))
    if widget.get_division_cost() is not None:
        print(f"Adding division cost {widget.get_division_cost()}")
        solver.add_costs(Split(constant=widget.get_division_cost()))

    start_time = time.time()
    solution = solver.solve()
    print(f"Solution took {time.time() - start_time} seconds")
    return solution, solver


def get_solution_nx_graph(solution, solver, cand_graph):
    node_selected = solver.get_variables(NodeSelected)
    edge_selected = solver.get_variables(EdgeSelected)

    selected_nodes = [
        node for node in cand_graph.nodes if solution[node_selected[node]] > 0.5
    ]
    selected_edges = [
        edge for edge in cand_graph.edges if solution[edge_selected[edge]] > 0.5
    ]

    print(f"Selected nodes: {len(selected_nodes)}")
    print(f"Selected edges: {len(selected_edges)}")
    solution_graph = nx.edge_subgraph(cand_graph, selected_edges)
    return solution_graph
