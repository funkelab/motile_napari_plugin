import napari
import pandas as pd
from motile_plugin.data_model import SolutionTracks
from motile_plugin.data_views.views.tree_view.tree_widget_utils import (
    extract_sorted_tracks,
)
from motile_toolbox.visualization.napari_utils import assign_tracklet_ids


def test_track_df(graph_2d):
    tracks = SolutionTracks(graph=graph_2d, ndim=3)

    assert tracks.get_area("0_1") == 1245
    assert tracks.get_area("1_2") is None

    tracks.graph, _, _ = assign_tracklet_ids(tracks.graph)

    colormap = napari.utils.colormaps.label_colormap(
        49,
        seed=0.5,
        background_value=0,
    )

    track_df = extract_sorted_tracks(tracks, colormap)
    assert isinstance(track_df, pd.DataFrame)
    assert track_df.loc[track_df["node_id"] == "0_1", "area"].values[0] == 1245
    assert track_df.loc[track_df["node_id"] == "1_2", "area"].values[0] == 0
    assert track_df["area"].notna().all()
