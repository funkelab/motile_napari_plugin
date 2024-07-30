import copy
from typing import Dict, List

import napari
import numpy as np
from napari.utils import Colormap, CyclicLabelColormap, DirectLabelColormap
from napari.utils.colormaps import label_colormap


def create_base_cyclic_colormap() -> CyclicLabelColormap:
    """Create the standard labels layer colormap"""

    return label_colormap(
        49,
        seed=0.5,
        background_value=0,
    )


def create_track_layer_colormap(
    tracks: napari.layers.Tracks, base_colormap: CyclicLabelColormap, name: str
) -> None:
    """Create a colormap for the label colors in the napari Labels layer"""

    labels = []
    colors = []

    for label in np.unique(tracks.properties["track_id"]):
        if label != 0:
            labels.append(label)
            colors.append(base_colormap.map(label))

    n_labels = len(labels)
    controls = (
        np.arange(n_labels + 1) / n_labels
    )  # Ensure controls are evenly spaced

    # Create a Colormap with discrete mapping using RGBA colors
    colormap = Colormap(
        colors=colors, controls=controls, name=name, interpolation="zero"
    )

    # Register the colormap
    from napari.utils.colormaps import AVAILABLE_COLORMAPS

    AVAILABLE_COLORMAPS[name] = colormap


def create_label_color_dict(
    labels: List[int], colormap: CyclicLabelColormap
) -> Dict:
    """Extract the label colors to generate a base colormap, but keep opacity at 0"""

    color_dict_rgb = {None: [0.0, 0.0, 0.0, 0.0]}

    # Iterate over unique labels
    for label in labels:
        color = colormap.map(label)
        color[-1] = (
            0.6  # Set opacity to 0 (will be replaced when a label is visible/invisible/selected)
        )
        color_dict_rgb[label] = color

    return color_dict_rgb


def create_selection_label_cmap(
    color_dict_rgb: Dict, highlighted: List[int]
) -> DirectLabelColormap:
    """Generates a label colormap with three possible opacity values (0 for invisibible labels, 0.6 for visible labels, and 1 for selected labels)"""

    color_dict_rgb_temp = copy.deepcopy(color_dict_rgb)
    for label in highlighted:
        if label != 0:
            color_dict_rgb_temp[label][-1] = 1  # set opacity to full

    return DirectLabelColormap(color_dict=color_dict_rgb_temp)
