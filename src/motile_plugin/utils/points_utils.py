import napari
import napari.layers
import numpy as np
import pandas as pd


def construct_points_layer(data: pd.DataFrame, name) -> napari.layers.Points:
    """Create a point layer for the nodes in the table"""

    edge_color = [1, 1, 1, 1]

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
        name=name,
        edge_color=edge_color,
        properties=properties,
        face_color=colors,
        size=5,
        symbol=symbols,
    )
