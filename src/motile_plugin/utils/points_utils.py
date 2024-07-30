import napari
import napari.layers
import numpy as np
from motile_plugin.backend.motile_run import MotileRun

from .tree_widget_utils import extract_sorted_tracks


def construct_points_layer(
    run: MotileRun, colormap: napari.utils.CyclicLabelColormap
) -> napari.layers.Points:
    """Create a point layer for the nodes in the table"""

    edge_color = [1, 1, 1, 1]

    data = extract_sorted_tracks(run.tracks, colormap)

    # Collect point data, colors and symbols directly from the track_data dataframe
    colors = np.array(data["color"].tolist()) / 255
    annotate_indices = data[
        data["annotated"]
    ].index  # manual edits should be displayed in a different color
    colors[annotate_indices] = np.array([1, 0, 0, 1])
    symbols = np.array(data["symbol"].tolist())
    properties = data

    if "z" in data.columns:
        points = np.column_stack(
            (
                data["t"].values,
                data["z"].values,
                data["y"].values,
                data["x"].values,
            )
        )
    else:
        points = data[["t", "y", "x"]].values

    # Add points layer (single time point) to the Napari viewer
    return napari.layers.Points(
        points,
        name=run.run_name + "_points",
        edge_color=edge_color,
        properties=properties,
        face_color=colors,
        size=5,
        symbol=symbols,
    )
