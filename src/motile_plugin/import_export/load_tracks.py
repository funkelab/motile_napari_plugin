from csv import DictReader
from typing import Any

import networkx as nx
import numpy as np
from motile_toolbox.candidate_graph import NodeAttr

from motile_plugin.data_model import SolutionTracks


def convert_value(value: Any):
    """Converts the given value to float or int if possible, otherwise returns it as is"""

    try:
        # Try to convert to integer
        int_value = int(value)
        if str(int_value) == value:
            return int_value
    except ValueError:
        pass

    try:
        # Try to convert to float
        float_value = float(value)
        if str(float_value) == value:
            return float_value
    except ValueError:
        pass

    # If conversion to int or float fails, return the original value
    return value


def tracks_from_csv(
    csvfile: str,
    selected_columns: dict,
    extra_columns: dict,
    segmentation: np.ndarray | None = None,
    scale: list[float] | None = None,
) -> SolutionTracks:
    """Assumes a csv similar to that created from "export tracks to csv" with columns:
        t,[z],y,x,id,parent_id,[seg_id]
    Cells without a parent_id will have an empty string or a -1 for the parent_id.

    Args:
        csvfile (str):
            path to the csv to load
        selected_columns (dict): a dictionary mapping the attributes "t", "z", "y", "x", "id", "seg_id", "parent_id" to columns of the csv file
        extra_columns (dict): a dictionary mapping optional additonal attributes to columns of the csv file
        segmentation (np.ndarray | None, optional):
            An optional accompanying segmentation.
            If provided, assumes that the seg_id column in the csv file exists and
            corresponds to the label ids in the segmentation array

    Returns:
        Tracks: a tracks object ready to be visualized with
            TracksViewer.view_external_tracks
    """
    graph = nx.DiGraph()
    with open(csvfile) as f:
        reader = DictReader(f)
        for row in reader:
            _id = row[selected_columns["id"]]
            if selected_columns["z"] != "Select Column":
                attrs = {
                    "pos": [
                        float(row[selected_columns["z"]]),
                        float(row[selected_columns["y"]]),
                        float(selected_columns["x"]),
                    ],
                    "time": int(row[selected_columns["t"]]),
                }
                ndims = 4
                scale = [1, *scale]  # assumes 1 for time step
            else:
                attrs = {
                    "pos": [
                        float(row[selected_columns["y"]]),
                        float(row[selected_columns["x"]]),
                    ],
                    "time": int(row[selected_columns["t"]]),
                }
                ndims = 3
                scale = [1, scale[1], scale[2]]
            if selected_columns["seg_id"] != "Select Column":
                attrs["seg_id"] = int(row[selected_columns["seg_id"]])
            for key in extra_columns:
                if extra_columns[key] != "Select Column":
                    attrs[key] = convert_value(
                        row[extra_columns[key]]
                    )  # try to convert strings to numerical values if possible

            graph.add_node(_id, **attrs)
            parent_id = row[selected_columns["parent_id"]].strip()
            if parent_id != "":
                parent_id = parent_id
                if parent_id != -1:
                    assert parent_id in graph.nodes, f"{_id} {parent_id}"
                    graph.add_edge(parent_id, _id)
    if segmentation is not None:
        segmentation = np.expand_dims(
            segmentation, axis=1
        )  # do we need to keep the empty hypothesis dim?
    tracks = SolutionTracks(
        graph=graph,
        segmentation=segmentation,
        pos_attr="pos",
        time_attr="time",
        ndim=ndims,
        scale=scale,
    )

    # compute the 'area' attribute if needed
    if tracks.segmentation is not None and "area" not in attrs:
        nodes = tracks.graph.nodes
        times = tracks.get_times(nodes)
        seg_ids = tracks.get_seg_ids(nodes, required=True)
        computed_attrs = tracks._compute_node_attrs(seg_ids, times)
        areas = computed_attrs[NodeAttr.AREA.value]
        tracks._set_nodes_attr(nodes, NodeAttr.AREA.value, areas)

    return tracks
