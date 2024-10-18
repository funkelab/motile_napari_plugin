from csv import DictReader

import networkx as nx
import numpy as np
from motile_plugin.core import Tracks


def tracks_from_csv(csvfile: str, segmentation: np.ndarray | None = None) -> Tracks:
    """Assumes a csv similar to that created from "export tracks to csv" with columns:
        t,[z],y,x,id,parent_id,[seg_id]
    Cells without a parent_id will have an empty string or a -1 for the parent_id.

    Args:
        csvfile (str):
            path to the csv to load
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
            _id = row["id"]
            attrs = {
                "pos": [float(row["y"]), float(row["x"])],
                "time": int(row["t"]),
            }
            if "seg_id" in row:
                attrs["seg_id"] = int(row["seg_id"])
            graph.add_node(_id, **attrs)
            parent_id = row["parent_id"].strip()
            if parent_id != "":
                parent_id = parent_id
                if parent_id != -1:
                    assert parent_id in graph.nodes, f"{_id} {parent_id}"
                    graph.add_edge(parent_id, _id)
    tracks = Tracks(
        graph=graph, segmentation=segmentation, pos_attr=("pos"), time_attr="time"
    )
    return tracks
