from dataclasses import dataclass
from typing import Any

import napari
import numpy as np
from motile_toolbox.candidate_graph import NodeAttr
from motile_toolbox.visualization import to_napari_tracks_layer
from napari.layers import Labels, Points, Tracks
from psygnal import Signal

from motile_plugin.backend.motile_run import MotileRun


@dataclass
class TrackingLayerGroup:
    tracks_layer: napari.layers.Tracks | None = None
    seg_layer: napari.layers.Labels | None = None
    points_layer: napari.layers.Points | None = None


class TrackingViewController:
    selection_updated = Signal(object)
    tracking_layers_updated = Signal(object)

    @classmethod
    def get_instance(cls, viewer=None):
        if not hasattr(cls, "_instance"):
            print("Making new tracking view controller")
            if viewer is None:
                raise ValueError("Make a viewer first please!")
            cls._instance = TrackingViewController(viewer)
        return cls._instance

    def __init__(self, viewer: napari.viewer):
        self.viewer = viewer
        self.selected_nodes = []
        self.tracking_layers: TrackingLayerGroup = TrackingLayerGroup()
        self.colormap = napari.utils.colormaps.label_colormap()

    def remove_napari_layer(self, layer: napari.layers.Layer | None) -> None:
        """Remove a layer from the napari viewer, if present"""
        if layer and layer in self.viewer.layers:
            self.viewer.layers.remove(layer)

    def remove_napari_layers(self):
        self.remove_napari_layer(self.tracking_layers.tracks_layer)
        self.remove_napari_layer(self.tracking_layers.seg_layer)
        self.remove_napari_layer(self.tracking_layers.points_layer)

    def add_napari_layers(self):
        if self.tracking_layers.tracks_layer is not None:
            self.viewer.add_layer(self.tracking_layers.tracks_layer)
        if self.tracking_layers.seg_layer is not None:
            self.viewer.add_layer(self.tracking_layers.seg_layer)
        if self.tracking_layers.points_layer is not None:
            self.viewer.add_layer(self.tracking_layers.points_layer)

    def update_napari_layers(self, run: MotileRun) -> None:
        """Remove the old napari layers and update them according to the run output.
        Will create new segmentation and tracks layers and add them to the viewer.

        Args:
            run (MotileRun): The run outputs to visualize in napari.
        """
        # Remove old layers if necessary
        self.remove_napari_layers()

        # Create new layers
        if run.output_segmentation is not None:
            self.tracking_layers.seg_layer = Labels(
                run.output_segmentation[:, 0],
                name=run.run_name + "_seg",
                colormap=self.colormap,
            )
        else:
            self.tracking_layers.seg_layer = None

        if run.tracks is None or run.tracks.number_of_nodes() == 0:
            self.tracking_layers.tracks_layer = None
            self.tracking_layers.points_layer = None
        else:
            # add tracks layer
            track_data, track_props, track_edges = to_napari_tracks_layer(
                run.tracks
            )
            self.tracking_layers.tracks_layer = Tracks(
                track_data,
                properties=track_props,
                graph=track_edges,
                name=run.run_name + "_tracks",
                tail_length=3,
            )
            node_ids = np.array(run.tracks.nodes())
            points = [
                [
                    data[NodeAttr.TIME.value],
                ]
                + list(data[NodeAttr.POS.value])
                for _, data in run.tracks.nodes(data=True)
            ]
            self.tracking_layers.points_layer = Points(
                name=run.run_name + "_points",
                data=points,
                features={"node_id": node_ids},
                face_colormap=self.colormap,
            )
        self.tracking_layers_updated.emit(run)
        self.add_napari_layers()

    def select_node(self, node_id: Any, add_to_existing=False):
        if add_to_existing:
            self.selected_nodes.append(node_id)
        else:
            self.selected_nodes = [node_id]
        print("Selected nodes: ", self.selected_nodes)
        self.selection_updated.emit(self.selected_nodes)
        self._set_napari_view()
        # should probably also update selection in napari layers

    def _set_napari_view(self) -> None:
        """Adjust the current_step of the viewer to jump to the last item of the selected_nodes list"""

        if len(self.selected_nodes) > 0:
            node = self.selected_nodes[-1]

            # Check for 'z' key and update step if exists
            step = list(self.viewer.dims.current_step)
            # old_time = step[0]  # for checking later
            # new_time = node["t"]
            step[0] = node["t"]
            if "z" in node:
                z = node["z"]
                step[1] = int(z)
            self.viewer.dims.current_step = step

            # check whether the new coordinates are inside or outside the field of view, then adjust the camera if needed
            if self.viewer.dims.ndisplay == 2:  # no 3D solution yet
                camera_pos = self.viewer.window._qt_window._qt_viewer.view.camera.get_state()[
                    "rect"
                ]._pos  # top left corner
                camera_size = self.viewer.window._qt_window._qt_viewer.view.camera.get_state()[
                    "rect"
                ].size

                print(f"{node['x']=}")
                print(f"{camera_pos[0]=}")
                print(f"{camera_size[0]=}")
                if not (
                    (
                        node["x"] > camera_pos[0]
                        and node["x"] < camera_pos[0] + camera_size[0]
                    )
                    and (
                        node["y"] > camera_pos[1]
                        and node["y"] < camera_pos[1] + camera_size[1]
                    )
                ):
                    camera_center = self.viewer.camera.center

                    self.viewer.camera.center = (
                        camera_center[0],
                        node["y"],
                        node["x"],
                    )
