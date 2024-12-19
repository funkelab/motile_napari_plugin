import ast

import networkx as nx
import numpy as np
import pandas as pd
from motile_toolbox.candidate_graph import NodeAttr

from motile_tracker.data_model import SolutionTracks


def _test_valid(df: pd.DataFrame, segmentation: np.ndarray, scale: list[float]) -> bool:
    """Test if the segmentation pixel value for the coordinates of first node corresponds
    with the provided seg_id as a basic sanity check that the csv file matches with the
    segmentation file
    """
    assert (
        NodeAttr.SEG_ID.value in df.columns
    ), f"Missing {NodeAttr.SEG_ID.value} attribute"
    row = df.iloc[0]
    pos = (
        [row[NodeAttr.TIME.value], row["z"], row["y"], row["x"]]
        if "z" in df.columns
        else [row[NodeAttr.TIME.value], row["y"], row["x"]]
    )
    seg_id = row[NodeAttr.SEG_ID.value]
    coordinates = [
        int(coord / scale_value) for coord, scale_value in zip(pos, scale, strict=True)
    ]
    value = segmentation[tuple(coordinates)]
    return value == seg_id


def tracks_from_df(
    df: pd.DataFrame,
    segmentation: np.ndarray | None = None,
    scale: list[float] | None = None,
) -> SolutionTracks:
    """Turns a pandas data frame with columns:
        t,[z],y,x,id,parent_id,[seg_id], [optional custom attr 1], ...
    into a SolutionTracks object.

    Cells without a parent_id will have an empty string or a -1 for the parent_id.

    Args:
        df (pd.DataFrame):
            a pandas DataFrame containing columns
            t,[z],y,x,id,parent_id,[seg_id], [optional custom attr 1], ...
        segmentation (np.ndarray | None, optional):
            An optional accompanying segmentation.
            If provided, assumes that the seg_id column in the dataframe exists and
            corresponds to the label ids in the segmentation array. Defaults to None.
        scale (list[float] | None, optional):
            The scale of the segmentation (including the time dimension). Defaults to None.

    Returns:
        SolutionTracks: a solution tracks object
    Raises:
        ValueError: if the segmentation IDs in the dataframe do not match the provided
            segmentation
    """

    required_columns = ["id", NodeAttr.TIME.value, "y", "x", "parent_id"]
    for column in required_columns:
        assert (
            column in df.columns
        ), f"Required column {column} not found in dataframe columns {df.columns}"

    if segmentation is not None and not _test_valid(df, segmentation, scale):
        raise ValueError(
            "Segmentation ids in dataframe do not match values in segmentation. Is it possible that you loaded the wrong combination of csv file and segmentation, or that the scaling information you provided is incorrect?"
        )

    # Convert custom attributes stored as strings back to lists
    for col in df.columns:
        if col not in [
            NodeAttr.TIME.value,
            "z",
            "y",
            "x",
            "id",
            "parent_id",
            NodeAttr.SEG_ID.value,
        ]:
            df[col] = df[col].apply(
                lambda x: ast.literal_eval(x)
                if isinstance(x, str) and x.startswith("[") and x.endswith("]")
                else x
            )

    # sort the dataframe to ensure that parents get added to the graph before children
    df = df.sort_values(NodeAttr.TIME.value)
    graph = nx.DiGraph()
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        _id = row["id"]
        parent_id = row["parent_id"]
        if "z" in df.columns:
            pos = [row["z"], row["y"], row["x"]]
            ndims = 4
            del row_dict["z"]
        else:
            pos = [row["y"], row["x"]]
            ndims = 3

        attrs = {
            NodeAttr.TIME.value: row["time"],
            NodeAttr.POS.value: pos,
        }

        # add all other columns into the attributes
        for attr in required_columns:
            del row_dict[attr]
        attrs.update(row_dict)

        if "seg_id" in df.columns:
            attrs[NodeAttr.TRACK_ID.value] = row["seg_id"]

        # add the node to the graph
        graph.add_node(_id, **attrs)

        # add the edge to the graph, if the node has a parent
        # note: this loading format does not support edge attributes
        if not pd.isna(parent_id) and parent_id != -1:
            assert (
                parent_id in graph.nodes
            ), f"Parent id {parent_id} of node {_id} not in graph yet"
            graph.add_edge(parent_id, _id)

    if segmentation is not None:
        # add dummy hypothesis dimension (for now)
        segmentation = np.expand_dims(segmentation, axis=1)

    tracks = SolutionTracks(
        graph=graph,
        segmentation=segmentation,
        pos_attr=NodeAttr.POS.value,
        time_attr=NodeAttr.TIME.value,
        ndim=ndims,
        scale=scale,
    )

    # compute the 'area' attribute if needed
    if tracks.segmentation is not None and NodeAttr.AREA.value not in df.columns:
        nodes = tracks.graph.nodes
        times = tracks.get_times(nodes)
        seg_ids = tracks.get_seg_ids(nodes, required=True)
        computed_attrs = tracks._compute_node_attrs(seg_ids, times)
        areas = computed_attrs[NodeAttr.AREA.value]
        tracks._set_nodes_attr(nodes, NodeAttr.AREA.value, areas)

    return tracks
