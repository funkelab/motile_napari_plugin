import copy
from typing import Dict, List

from napari.utils import CyclicLabelColormap, DirectLabelColormap


def create_label_color_dict(
    labels: List[int], colormap: CyclicLabelColormap
) -> Dict:
    """Extract the label colors to generate a base colormap, but keep opacity at 0"""

    color_dict_rgb = {None: [0.0, 0.0, 0.0, 0.0]}

    # Iterate over unique labels
    for label in labels:
        color = colormap.map(label)
        color[
            -1
        ] = 0  # Set opacity to 0 (will be replaced when a label is visible/invisible/selected)
        color_dict_rgb[label] = color

    return color_dict_rgb


def create_selection_label_cmap(
    color_dict_rgb: Dict, visible: List[int] | str, highlighted: List[int]
) -> DirectLabelColormap:
    """Generates a label colormap with three possible opacity values (0 for invisibible labels, 0.6 for visible labels, and 1 for selected labels)"""

    color_dict_rgb_temp = copy.deepcopy(color_dict_rgb)
    if visible == "all":
        for key in color_dict_rgb_temp:
            if key is not None:
                color_dict_rgb_temp[key][-1] = 0.6  # set opacity to 0.6
    else:
        for label in visible:
            color_dict_rgb_temp[label][-1] = 0.6  # set opacity to 0.6

    for label in highlighted:
        if label != 0:
            color_dict_rgb_temp[label][-1] = 1  # set opacity to full

    return DirectLabelColormap(color_dict=color_dict_rgb_temp)
