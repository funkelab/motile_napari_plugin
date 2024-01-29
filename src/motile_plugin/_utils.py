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

def get_cand_graph_from_segmentation(
    segmentation, max_edge_distance, pos_labels=["y", "x"]
):
    """_summary_

    Args:
        segmentation (np.array): A numpy array with shape (t, [z,], y, x)
    """
    # add nodes
    node_frame_dict = (
        {}
    )  # construct a dictionary from time frame to node_id for efficiency
    cand_graph = nx.DiGraph()

    for t in range(len(segmentation)):
        nodes_in_frame = []
        props = regionprops(segmentation[t])
        for i, regionprop in enumerate(props):
            node_id = f"{t}_{regionprop.label}"  # TODO: previously node_id= f"{t}_{i}"
            attrs = {
                "t": t,
                "segmentation_id": regionprop.label,
                "area": regionprop.area,
            }
            centroid = regionprop.centroid  # [z,] y, x
            for label, value in zip(pos_labels, centroid):
                attrs[label] = value
            cand_graph.add_node(node_id, **attrs)
            nodes_in_frame.append(node_id)
        node_frame_dict[t] = nodes_in_frame

    print(f"Candidate nodes: {cand_graph.number_of_nodes()}")

    # add edges
    frames = sorted(node_frame_dict.keys())
    for frame in tqdm(frames):
        if frame + 1 not in node_frame_dict:
            continue
        next_nodes = node_frame_dict[frame + 1]
        next_locs = [
            get_location(cand_graph.nodes[n], loc_keys=pos_labels) for n in next_nodes
        ]
        for node in node_frame_dict[frame]:
            loc = get_location(cand_graph.nodes[node], loc_keys=pos_labels)
            for next_id, next_loc in zip(next_nodes, next_locs):
                dist = math.dist(next_loc, loc)
                attrs = {
                    "dist": dist,
                }
                if dist < max_edge_distance:
                    cand_graph.add_edge(node, next_id, **attrs)

    print(f"Candidate edges: {cand_graph.number_of_edges()}")
    return cand_graph



def solve_with_motile(cand_graph, widget):
    motile_cand_graph = TrackGraph(cand_graph)
    solver = Solver(motile_cand_graph)

    solver.add_constraints(MaxChildren(widget.get_max_children()))
    solver.add_constraints(MaxParents(1))

    if widget.get_distance_weight() is not None:
        solver.add_costs(EdgeSelection(widget.get_distance_weight(), attribute="dist", constant=widget.get_distance_offset()))
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



def assign_tracklet_ids(graph):
    """Add a tracklet_id attribute to a graph by removing division edges,
    assigning one id to each connected component.
    Designed as a helper for visualizing the graph in the napari Tracks layer.

    Args:
        graph (nx.DiGraph): A networkx graph with a tracking solution

    Returns:
        nx.DiGraph: The same graph with the tracklet_id assigned. Probably
        occurrs in place but returned just to be clear.
    """
    graph_copy = graph.copy()

    parents = [node for node, degree in graph.out_degree() if degree >= 2]
    intertrack_edges = []

    # Remove all intertrack edges from a copy of the original graph
    for parent in parents:
        daughters = [child for p, child in graph.out_edges(parent)]
        for daughter in daughters:
            graph_copy.remove_edge(parent, daughter)
            intertrack_edges.append((parent, daughter))

    track_id = 0
    for tracklet in nx.weakly_connected_components(graph_copy):
        nx.set_node_attributes(
            graph, {node: {"tracklet_id": track_id} for node in tracklet}
        )
        track_id += 1
    return graph, intertrack_edges


def to_napari_tracks_layer(
    graph, frame_key="t", location_keys=("y", "x"), properties=()
):
    """Function to take a networkx graph and return the data needed to add to
    a napari tracks layer.

    Args:
        graph (nx.DiGraph): _description_
        frame_key (str, optional): Key in graph attributes containing time frame.
            Defaults to "t".
        location_keys (tuple, optional): Keys in graph node attributes containing
            location. Should be in order: (Z), Y, X. Defaults to ("y", "x").
        properties (tuple, optional): Keys in graph node attributes to add
            to the visualization layer. Defaults to (). NOTE: not working now :(

    Returns:
        data : array (N, D+1)
            Coordinates for N points in D+1 dimensions. ID,T,(Z),Y,X. The first
            axis is the integer ID of the track. D is either 3 or 4 for planar
            or volumetric timeseries respectively.
        properties : dict {str: array (N,)}
            Properties for each point. Each property should be an array of length N,
            where N is the number of points.
        graph : dict {int: list}
            Graph representing associations between tracks. Dictionary defines the
            mapping between a track ID and the parents of the track. This can be
            one (the track has one parent, and the parent has >=1 child) in the
            case of track splitting, or more than one (the track has multiple
            parents, but only one child) in the case of track merging.
    """
    napari_data = np.zeros((graph.number_of_nodes(), len(location_keys) + 2))
    napari_properties = {prop: np.zeros(graph.number_of_nodes()) for prop in properties}
    napari_edges = {}
    graph, intertrack_edges = assign_tracklet_ids(graph)
    for index, node in enumerate(graph.nodes(data=True)):
        node_id, data = node
        location = [data[loc_key] for loc_key in location_keys]
        napari_data[index] = [data["tracklet_id"], data[frame_key]] + location
        for prop in properties:
            if prop in data:
                napari_properties[prop][index] = data[prop]
    napari_edges = {}
    for parent, child in intertrack_edges:
        parent_track_id = graph.nodes[parent]["tracklet_id"]
        child_track_id = graph.nodes[child]["tracklet_id"]
        if child_track_id in napari_edges:
            napari_edges[child_track_id].append(parent_track_id)
        else:
            napari_edges[child_track_id] = [parent_track_id]
    return napari_data, napari_properties, napari_edges        
  