import csv
import json
from pathlib import Path

from motile_toolbox.candidate_graph.graph_attributes import NodeAttr

from motile_tracker.data_model import SolutionTracks


def export_solution_to_csv(solution: SolutionTracks, outfile: Path | str):
    """Export the tracks from this run to a csv with the following columns:
    t, [z], y, x, id, parent_id, track_id. Will also add all custom attributes (e.g. area, group)
    not in [NodeAttr.TIME.value, NodeAttr.POS.value, NodeAttr.SEG_ID.value, NodeAttr.TRACK_ID.value]
    Cells without a parent_id will have an empty string for the parent_id.
    Whether or not to include z is inferred from self.ndim
    """

    header = ["t", "z", "y", "x", "id", "parent_id", "track_id"]
    all_attributes = {
        key for _, attrs in solution.graph.nodes(data=True) for key in attrs
    }
    custom_attrs = [
        attr
        for attr in all_attributes
        if attr
        not in [
            NodeAttr.TIME.value,
            NodeAttr.POS.value,
            NodeAttr.SEG_ID.value,
            NodeAttr.TRACK_ID.value,
        ]
    ]
    for attr in custom_attrs:
        header.append(attr)

    if solution.ndim == 3:
        header = [header[0]] + header[2:]  # remove z

    with open(outfile, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for node_id in solution.graph.nodes():
            parents = list(solution.graph.predecessors(node_id))
            parent_id = "" if len(parents) == 0 else parents[0]
            track_id = solution.get_track_id(node_id)
            time = solution.get_time(node_id)
            position = solution.get_position(node_id)
            custom_attr = [
                json.dumps(solution._get_node_attr(node_id, attr, required=False))
                for attr in custom_attrs
            ]  # any other attributes, such as area or group
            row = [
                time,
                *position,
                node_id,
                parent_id,
                track_id,
                *custom_attr,
            ]
            row = ["" if value is None else value for value in row]
            writer.writerow(row)
