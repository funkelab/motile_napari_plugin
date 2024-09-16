import napari
import pandas as pd
from motile_plugin.core import Tracks
from motile_plugin.utils.tree_widget_utils import extract_sorted_tracks
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids
import networkx as nx
import numpy as np

Tracks.model_rebuild()


def test_track_df(graph_2d):

    tracks = Tracks(graph=graph_2d)

    assert tracks.get_area("0_1") == 1245
    assert tracks.get_area("1_1") is None

    tracks.graph, _ = assign_tracklet_ids(tracks.graph)

    colormap = napari.utils.colormaps.label_colormap(
        49,
        seed=0.5,
        background_value=0,
    )

    track_df = extract_sorted_tracks(tracks, colormap)
    assert isinstance(track_df, pd.DataFrame)
    assert track_df.loc[track_df["node_id"] == "0_1", "area"].values[0] == 1245
    assert track_df.loc[track_df["node_id"] == "1_1", "area"].values[0] == 0
    assert track_df["area"].notna().all()
