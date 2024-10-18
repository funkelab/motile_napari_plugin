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
            segmentation ids and hypothesis ids have to be stored in the graph so we
            can map them back. Assumes tracket ids have already been assigned.
        segmentation (np.ndarray): Original (potentially multi-hypothesis)
            segmentation with dimensions (t,h,[z],y,x), where h is 1 for single
            input segmentation.

    Returns:
        np.ndarray: Relabeled segmentation array where nodes in same track share same
            id with shape (t,1,[z],y,x)
    """
    output_shape = (segmentation.shape[0], 1, *segmentation.shape[2:])
    tracked_masks = np.zeros_like(segmentation, shape=output_shape)
    for node, _data in solution_nx_graph.nodes(data=True):
        time_frame = solution_nx_graph.nodes[node][NodeAttr.TIME.value]
        previous_seg_id = solution_nx_graph.nodes[node][NodeAttr.SEG_ID.value]
        assert previous_seg_id != 0
        tracklet_id = solution_nx_graph.nodes[node]["tracklet_id"]
        hypothesis_id = solution_nx_graph.nodes[node].get(NodeAttr.SEG_HYPO.value, 0)
        previous_seg_mask = segmentation[time_frame, hypothesis_id] == previous_seg_id
        tracked_masks[time_frame, 0][previous_seg_mask] = tracklet_id
    return tracked_masks
