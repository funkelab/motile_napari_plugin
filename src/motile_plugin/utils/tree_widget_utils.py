import copy
from typing import Any, Callable, Dict, List, Tuple

import napari.layers
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgba
from motile_toolbox.candidate_graph import NodeAttr
from napari import Viewer
from napari.utils import Colormap, DirectLabelColormap
from PyQt5.QtCore import Qt
from qtpy.QtWidgets import QPushButton


def extract_sorted_tracks(
    solution_nx_graph: nx.DiGraph,
    colormap: napari.utils.CyclicLabelColormap,
    time_attr=NodeAttr.TIME.value,
    pos_attr=NodeAttr.POS.value,
) -> pd.DataFrame:
    """
    Extract the information of individual tracks required for constructing the pyqtgraph plot. Follows the same logic as the relabel_segmentation
    function from the Motile toolbox.

    Args:
        solution_nx_graph (nx.DiGraph): NetworkX graph with the solution to use
            for relabeling. Nodes not in the graph will be removed from segmentation.
            Original segmentation IDs and hypothesis IDs have to be stored in the graph
            so we can map them back.
        labels (napari.layers.labels.labels.Labels): the labels layer to which the tracking solution belongs.
            It is used to extract the corresponding label color for the nodes and edges.

    Returns:
        List: pd.DataFrame with columns 't', 'node_id', 'track_id', 'color', 'x', 'y', ('z'), 'index', 'parent_id', and 'parent_track_id',
        containing all information needed to construct the pyqtgraph plot.
    """
    if solution_nx_graph is None:
        return None

    track_list = []
    counter = 0
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
            key=lambda node: solution_nx_graph.nodes[node][time_attr],
        )

        parent_track_id = None
        for node in sorted_nodes:
            node_data = solution_nx_graph.nodes[node]
            if isinstance(pos_attr, (list, tuple)):
                pos = [node_data[dim] for dim in pos_attr]
            else:
                pos = node_data[pos_attr]
            annotated = False
            if node in parent_nodes:
                state = "fork"  # can we change this to NodeAttr.STATE.value or equivalent?
                symbol = "triangle_up"
            elif node in end_nodes:
                state = "endpoint"  # can we change this to NodeAttr.STATE.value or equivalent?
                symbol = "x"
            else:
                state = "intermittent"
                symbol = "disc"

            # also check for manual annotations
            if node_data.get("fork") is True:
                state = "fork"  # can we change this to NodeAttr.STATE.value or equivalent?
                symbol = "triangle_up"
                annotated = True
            if node_data.get("endpoint") is True:
                state = "endpoint"  # can we change this to NodeAttr.STATE.value or equivalent?
                symbol = "x"
                annotated = True

            track_id = solution_nx_graph.nodes[node]["tracklet_id"]
            track_dict = {
                "t": node_data[time_attr],
                "node_id": node,
                "track_id": track_id,
                "color": colormap.map(track_id) * 255,
                "x": pos[-1],
                "y": pos[-2],
                "index": counter,
                "parent_id": 0,
                "parent_track_id": 0,
                "state": state,
                "symbol": symbol,
                "annotated": annotated,
            }

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
            counter += 1

        parent_mapping.append(
            {"track_id": id_counter, "parent_track_id": parent_track_id}
        )
        id_counter += 1

    x_axis_order = sort_track_ids(parent_mapping)

    for node in track_list:
        node["x_axis_pos"] = x_axis_order.index(node["track_id"])

    return pd.DataFrame(track_list)


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


def get_existing_pins(solution_nx_graph: nx.DiGraph) -> List[Tuple[str, str]]:
    """Extract a list of the pinned edges from this run.

    Args:
        solution_nx_graph (nx.DiGraph): NetworkX graph with the solution to use
        for relabeling.

    Returns:
        list: List of tuples containing the node_ids for pinned edges (only those with value True, since the ones with value False will not be visible in the graph).

    """

    pinned_edges = []
    for u, v, data in solution_nx_graph.edges(data=True):
        if data.get("pinned") is True:
            pinned_edges.append((u, v))

    return pinned_edges


def bind_key_with_condition(
    viewer: Viewer,
    key: str,
    button: QPushButton,
    target_function: Callable[[Any], None],
) -> None:
    """Binds a key to a function, only triggering if the button is enabled."""

    @viewer.bind_key(key, overwrite=True)
    def wrapped_function(event=None):
        if button.isEnabled():
            target_function()


def normalize_modifiers(modifiers):
    """Normalize the event modifiers to Qt.KeyboardModifiers."""

    if isinstance(modifiers, tuple):
        # Convert to Qt.KeyboardModifiers
        qt_modifiers = Qt.KeyboardModifiers()
        if "Shift" in modifiers:
            qt_modifiers |= Qt.ShiftModifier
        if "Ctrl" in modifiers or "Control" in modifiers:
            qt_modifiers |= Qt.ControlModifier
        if "Alt" in modifiers:
            qt_modifiers |= Qt.AltModifier
        if "Meta" in modifiers:
            qt_modifiers |= Qt.MetaModifier
        return qt_modifiers

    return modifiers


def create_colormap(tracked_labels: napari.layers.Labels, name: str) -> None:
    """Create a colormap for the label colors in the napari Labels layer"""

    labels = []
    colors = []
    for label in np.unique(tracked_labels.data):
        if label != 0:
            labels.append(label)
            colors.append(tracked_labels.get_color(label))

    n_labels = len(labels)
    controls = (
        np.arange(n_labels + 1) / n_labels
    )  # Ensure controls are evenly spaced

    # Create a Colormap with discrete mapping using RGBA colors
    colormap = Colormap(
        colors=colors, controls=controls, name=name, interpolation="zero"
    )

    # Register the colormap
    from napari.utils.colormaps import AVAILABLE_COLORMAPS

    AVAILABLE_COLORMAPS[name] = colormap


def create_selection_colormap(
    tracked_labels: napari.layers.Labels, name: str, selection: List[int]
) -> None:
    """Create a colormap for the label colors in the napari Labels layer"""

    labels = []
    colors = []
    for label in selection:
        if label != 0:
            labels.append(label)
            colors.append(tracked_labels.get_color(label))

    n_labels = len(labels)
    controls = (
        np.arange(n_labels + 1) / n_labels
    )  # Ensure controls are evenly spaced

    # Create a Colormap with discrete mapping using RGBA colors
    colormap = Colormap(
        colors=colors, controls=controls, name=name, interpolation="zero"
    )

    # Register the colormap
    from napari.utils.colormaps import AVAILABLE_COLORMAPS

    AVAILABLE_COLORMAPS[name] = colormap


def create_label_color_dict(
    labels: List[int], labels_layer: napari.layers.Labels
) -> Dict:
    """Extract the label colors to generate a base colormap, but keep opacity at 0"""

    color_dict_rgb = {None: (0.0, 0.0, 0.0, 0.0)}

    # Iterate over unique labels
    for label in labels:
        color = list(to_rgba(labels_layer.get_color(label)))
        color[
            -1
        ] = 0  # Set opacity to 0 (will be replaced when a label is selected)
        color_dict_rgb[label] = color

    return color_dict_rgb


def create_selection_label_cmap(
    color_dict_rgb: Dict, visible: List[int]
) -> DirectLabelColormap:
    """Generates a label colormap with only a selection visible"""

    color_dict_rgb_temp = copy.deepcopy(color_dict_rgb)
    for label in visible:
        if label != 0:
            color_dict_rgb_temp[label][-1] = 1  # set opacity to full

    return DirectLabelColormap(color_dict=color_dict_rgb_temp)


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
