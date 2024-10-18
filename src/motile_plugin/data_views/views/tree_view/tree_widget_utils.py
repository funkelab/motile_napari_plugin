from __future__ import annotations

import napari.layers
import networkx as nx
import numpy as np
import pandas as pd
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr

from motile_plugin.data_model import NodeType, Tracks


def extract_sorted_tracks(
    tracks: Tracks,
    colormap: napari.utils.CyclicLabelColormap,
    prev_df: pd.DataFrame | None = None,
) -> pd.DataFrame | None:
    """
    Extract the information of individual tracks required for constructing the pyqtgraph plot. Follows the same logic as the relabel_segmentation
    function from the Motile toolbox.

    Args:
        tracks (motile_plugin.core.Tracks): A tracks object containing a graph
            to be converted into a dataframe.
        colormap (napari.utils.CyclicLabelColormap): The colormap to use to
            extract the color of each node from the track ID
        prev_df (pd.DataFrame, Optional). Dataframe that holds the previous track_df, including the order of the tracks.

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
        positions = tracks.get_positions(sorted_nodes).tolist()

        parent_track_id = None
        for node, pos in zip(sorted_nodes, positions, strict=False):
            if node in parent_nodes:
                state = NodeType.SPLIT
                symbol = "t1"
            elif node in end_nodes:
                state = NodeType.END
                symbol = "x"
            else:
                state = NodeType.CONTINUE
                symbol = "o"

            track_id = tracks.get_track_id(node)
            track_dict = {
                "t": tracks.get_time(node),
                "node_id": node,
                "track_id": track_id,
                "color": np.concatenate((colormap.map(track_id)[:3] * 255, [255])),
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
                        NodeAttr.TRACK_ID.value
                    ]
                track_dict["parent_track_id"] = parent_track_id

            else:
                parent_track_id = 0
                track_dict["parent_id"] = 0
                track_dict["parent_track_id"] = parent_track_id

            track_list.append(track_dict)

        parent_mapping.append(
            {"track_id": track_id, "parent_track_id": parent_track_id, "node_id": node}
        )

    x_axis_order = sort_track_ids(parent_mapping, prev_df)

    for node in track_list:
        node["x_axis_pos"] = x_axis_order.index(node["track_id"])

    df = pd.DataFrame(track_list)
    if "area" in df.columns:
        df["area"] = df["area"].fillna(0)

    return df


def find_root(track_id: int, parent_map: dict) -> int:
    """Function to find the root associated with a track by tracing its lineage"""

    # Keep traversing a track is found where parent_track_id == 0 (i.e., it's a root)
    current_track = track_id
    while parent_map.get(current_track) != 0:
        current_track = parent_map.get(current_track)
    return current_track


def sort_track_ids(
    track_list: list[dict], prev_df: pd.DataFrame | None = None
) -> list[dict]:
    """
    Sort track IDs such to maintain left-first order in the tree formed by parent-child relationships.
    Used to determine the x-axis order of the tree plot.

    Args:
        track_list (list): List of dictionaries with 'track_id' and 'parent_track_id'.
        prev_df (pd.DataFrame, Optional). Dataframe that holds the previous track_df, including the order of the tracks.

    Returns:
        list: Ordered list of track IDs for the x-axis.
    """

    roots = [node["track_id"] for node in track_list if node["parent_track_id"] == 0]

    if prev_df is not None and not prev_df.empty:
        prev_roots = (
            prev_df.loc[prev_df["parent_track_id"] == 0, "track_id"].unique().tolist()
        )
        new_roots = set(roots) - set(
            prev_roots
        )  # Detect new roots (those in the current list but not in the previous list)

        # Create mappings for fast lookup
        track_id_map = {
            n["track_id"]: n["node_id"] for n in track_list
        }  # track_id -> node_id
        parent_map = {
            n["track_id"]: n["parent_track_id"] for n in track_list
        }  # track_id -> parent_track_id
        position_map = prev_df.set_index("node_id")[
            "x_axis_pos"
        ].to_dict()  # node_id -> x_axis_pos

        # Iterate over each new root and place it based on previous positions (to the right of its previous left neighbor)
        for new_root in new_roots:
            new_node_id = track_id_map.get(new_root)
            # if node_id of new root does not exist in track_id_map, it is a completely new node and we can skip the rest of the code below and add the new track at the end.
            if new_node_id and new_node_id in position_map:
                prev_pos = position_map[
                    new_node_id
                ]  # Get the previous position of the new root
                # Find which track was on the left of this new root based on previous x_axis_pos
                left_track = prev_df.loc[
                    prev_df["x_axis_pos"] == prev_pos - 1, "track_id"
                ].unique()
                if len(left_track) > 0:
                    left_track_id = left_track[0]  # Get the track ID of the left track
                    # Check if the left_track is a root or further downstream
                    if left_track_id not in roots:
                        # If the left_track is not a root, find the root associated with it
                        left_root = find_root(left_track_id, parent_map)
                    else:
                        # If left_track is already a root, use it as-is
                        left_root = left_track_id
                    # Find the index of the root where we need to insert the new root
                    left_ind = roots.index(left_root) if left_root in roots else -1
                else:
                    # If no left track is found, insert the new root at the beginning
                    left_ind = -1

                # Remove the new root from its current position and reinsert it after the left root
                roots.remove(new_root)
                roots.insert(left_ind + 1, new_root)

    # Final sorted order of roots
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


def extract_lineage_tree(graph: nx.DiGraph, node_id: str) -> list[str]:
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
