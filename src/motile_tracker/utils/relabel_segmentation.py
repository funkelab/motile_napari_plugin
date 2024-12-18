import networkx as nx
import numpy as np
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr


def relabel_segmentation(
    solution_nx_graph: nx.DiGraph,
    segmentation: np.ndarray,
) -> np.ndarray:
    """Relabel a segmentation based on tracking results so that nodes in same
    track share the same id. IDs do change at division.

    Args:
        solution_nx_graph (nx.DiGraph): Networkx graph with the solution to use
            for relabeling. Nodes not in graph will be removed from seg. Original
            segmentation ids have to be stored in the graph so we
            can map them back. Assumes tracklet ids have already been assigned.
        segmentation (np.ndarray): Original segmentation with dimensions (t,z],y,x)

    Returns:
        np.ndarray: Relabeled segmentation array where nodes in same track share same
            id with shape (t,[z],y,x)
    """
    tracked_masks = np.zeros_like(segmentation, shape=segmentation.shape)
    for node, _data in solution_nx_graph.nodes(data=True):
        time_frame = solution_nx_graph.nodes[node][NodeAttr.TIME.value]
        previous_seg_id = solution_nx_graph.nodes[node][NodeAttr.SEG_ID.value]
        assert previous_seg_id != 0
        tracklet_id = solution_nx_graph.nodes[node][NodeAttr.TRACK_ID.value]
        previous_seg_mask = segmentation[time_frame] == previous_seg_id
        tracked_masks[time_frame][previous_seg_mask] = tracklet_id
        solution_nx_graph.nodes[node][NodeAttr.SEG_ID.value] = tracklet_id
    return tracked_masks
