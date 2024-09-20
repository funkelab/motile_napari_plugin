from __future__ import annotations

import copy

import napari
import networkx as nx
import numpy as np
from motile_toolbox.visualization import to_napari_tracks_layer
from napari.utils import CyclicLabelColormap

from motile_plugin.data_model import Tracks


class TrackSpatialGraph(napari.layers.Graph):
    """Extended graph layer that holds the track information and emits and responds
    to dynamic visualization signals"""

    def __init__(
        self,
        viewer: napari.Viewer,
        tracks: Tracks,
        name: str,
        colormap: CyclicLabelColormap,
    ):
        if tracks is None or tracks.graph is None:
            raise ValueError("Need tracks to visualize")

        super().__init__(
            data=tracks.graph,
            name=name,
        )

        self.viewer = viewer
        self.colormap = colormap
