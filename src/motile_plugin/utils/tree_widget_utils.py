from typing import Dict, List

import napari.layers
import networkx as nx
import pandas as pd
from motile_plugin.core import NodeType, Tracks


def extract_sorted_tracks(
    tracks: Tracks,
    colormap: napari.utils.CyclicLabelColormap,
) -> pd.DataFrame | None:
    """
    Extract the information of individual tracks required for constructing the pyqtgraph plot. Follows the same logic as the relabel_segmentation
    function from the Motile toolbox.

    Args:
        tracks (motile_plugin.core.Tracks): A tracks object containing a graph
            to be converted into a dataframe.
        colormap (napari.utils.CyclicLabelColormap): The colormap to use to
            extract the color of each node from the track ID

    Returns:
        pd.DataFrame | None: data frame with all the information needed to
        construct the pyqtgraph plot. Columns are: 't', 'node_id', 'track_id',
        'color', 'x', 'y', ('z'), 'index', 'parent_id', 'parent_track_id',
        'state', 'symbol', and 'x_axis_pos'
    """
    if tracks is None or tracks.graph is None:
        return None

    solution_nx_graph = tracks.graph

    track_list = []
    id_counter = 1
    parent_mapping = []

    # Identify parent nodes (nodes with more than one child)
    parent_nodes = [n for (n, d) in solution_nx_graph.out_degree() if d > 1]
    end_nodes = [n for (n, d) in solution_nx_graph.out_degree() if d == 0]

    # Make a copy of the graph and remove outgoing edges from parent nodes to isolate tracks
    soln_copy = solution_nx_graph.copy()
    for parent_node in parent_nodes:
        out_edges = solution_nx_graph.out_edges(parent_node)
        soln_copy.remove_edges_from(out_edges)

    # Process each weakly connected component as a separate track
    for node_set in nx.weakly_connected_components(soln_copy):
        # Sort nodes in each weakly connected component by their time attribute to ensure correct order
        sorted_nodes = sorted(
            node_set,
            key=lambda node: tracks.get_time(node),
        )

        parent_track_id = None
        for node in sorted_nodes:
            pos = tracks.get_location(node)
            if node in parent_nodes:
                state = NodeType.SPLIT
                symbol = "t1"
            elif node in end_nodes:
                state = NodeType.END
                symbol = "x"
            else:
                state = NodeType.CONTINUE
                symbol = "o"

            track_id = solution_nx_graph.nodes[node]["tracklet_id"]
            track_dict = {
                "t": tracks.get_time(node),
                "node_id": node,
                "track_id": track_id,
                "color": colormap.map(track_id) * 255,
                "x": pos[-1],
                "y": pos[-2],
                "parent_id": 0,
                "parent_track_id": 0,
                "state": state,
                "symbol": symbol,
            }

            if tracks.get_area(node) is not None:
                track_dict["area"] = tracks.get_area(node)

            if len(pos) == 3:
                track_dict["z"] = pos[0]

            # Determine parent_id and parent_track_id
            predecessors = list(solution_nx_graph.predecessors(node))
            if predecessors:
                parent_id = predecessors[
                    0
                ]  # There should be only one predecessor in a lineage tree
                track_dict["parent_id"] = parent_id

                if parent_track_id is None:
                    parent_track_id = solution_nx_graph.nodes[parent_id][
                        "tracklet_id"
                    ]
                track_dict["parent_track_id"] = parent_track_id

            else:
                parent_track_id = 0
                track_dict["parent_id"] = 0
                track_dict["parent_track_id"] = parent_track_id

            track_list.append(track_dict)

        parent_mapping.append(
            {"track_id": id_counter, "parent_track_id": parent_track_id}
        )
        id_counter += 1

    x_axis_order = sort_track_ids(parent_mapping)

    for node in track_list:
        node["x_axis_pos"] = x_axis_order.index(node["track_id"])

    df = pd.DataFrame(track_list)
    if 'area' in df.columns:
        df['area'] = df['area'].fillna(0)
    
    return df

def sort_track_ids(track_list: List[Dict]) -> List[Dict]:
    """
    Sort track IDs such to maintain left-first order in the tree formed by parent-child relationships.
    Used to determine the x-axis order of the tree plot.

    Args:
        track_list (list): List of dictionaries with 'track_id' and 'parent_track_id'.

    Returns:
        list: Ordered list of track IDs for the x-axis.
    """

    roots = [
        node["track_id"] for node in track_list if node["parent_track_id"] == 0
    ]
    x_axis_order = list(roots)

    # Find the children of each of the starting points, and work down the tree.
    while len(roots) > 0:
        children_list = []
        for track_id in roots:
            children = [
                node["track_id"]
                for node in track_list
                if node["parent_track_id"] == track_id
            ]
            for i, child in enumerate(children):
                [children_list.append(child)]
                x_axis_order.insert(x_axis_order.index(track_id) + i, child)
        roots = children_list

    return x_axis_order


def extract_lineage_tree(graph: nx.DiGraph, node_id: str) -> List[str]:
    """Extract the entire lineage tree including horizontal relations for a given node"""

    # go up the tree to identify the root node
    root_node = node_id
    while True:
        predecessors = list(graph.predecessors(root_node))
        if not predecessors:
            break
        root_node = predecessors[0]

    # extract all descendants to get the full tree
    nodes = nx.descendants(graph, root_node)

    # include root
    nodes.add(root_node)

    return list(nodes)
