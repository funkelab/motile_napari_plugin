from __future__ import annotations

from typing import TYPE_CHECKING

import napari
import numpy as np
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr
from napari.utils import CyclicLabelColormap

if TYPE_CHECKING:
    from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer


class TrackLabels(napari.layers.Labels):
    """Extended labels layer that holds the track information and emits
    and responds to dynamics visualization signals"""

    @property
    def _type_string(self) -> str:
        return "labels"  # to make sure that the layer is treated as labels layer for saving

    def __init__(
        self,
        viewer: napari.Viewer,
        data: np.array,
        name: str,
        opacity: float,
        scale: tuple,
        tracks_viewer: TracksViewer,
    ):
        super().__init__(
            data=data,
            name=name,
            opacity=opacity,
            colormap=tracks_viewer.colormap,
            scale=scale,
        )

        self.viewer = viewer
        self.tracks_viewer = tracks_viewer
        self.nodes = list(self.tracks_viewer.tracks.graph.nodes)
        self.node_properties = {
            "node_id": self.nodes,
            "track_id": [
                data[NodeAttr.TRACK_ID.value]
                for _, data in self.tracks_viewer.tracks.graph.nodes(data=True)
            ],
            "t": [self.tracks_viewer.tracks.get_time(node) for node in self.nodes],
        }

        # Key bindings (should be specified both on the viewer (in tracks_viewer)
        # and on the layer to overwrite napari defaults)
        self.bind_key("q")(self.tracks_viewer.toggle_display_mode)
        self.bind_key("a")(self.tracks_viewer.create_edge)
        self.bind_key("d")(self.tracks_viewer.delete_node)
        self.bind_key("Delete")(self.tracks_viewer.delete_node)
        self.bind_key("b")(self.tracks_viewer.delete_edge)
        self.bind_key("s")(self.tracks_viewer.set_split_node)
        self.bind_key("e")(self.tracks_viewer.set_endpoint_node)
        self.bind_key("c")(self.tracks_viewer.set_linear_node)
        self.bind_key("z")(self.tracks_viewer.undo)
        self.bind_key("r")(self.tracks_viewer.redo)

        # Connect click events to node selection
        @self.mouse_drag_callbacks.append
        def click(_, event):
            if event.type == "mouse_press" and self.mode == "pan_zoom":
                label = self.get_value(
                    event.position,
                    view_direction=event.view_direction,
                    dims_displayed=event.dims_displayed,
                    world=True,
                )

                if label is not None and label != 0:
                    t_values = self.node_properties["t"]
                    track_ids = self.node_properties["track_id"]
                    index = np.where(
                        (t_values == event.position[0]) & (track_ids == label)
                    )[0]  # np.where returns a tuple with an array per dimension,
                    # here we apply it to a single dimension so take the first element
                    # (an array of indices fulfilling condition)
                    node_id = self.nodes[index[0]]
                    append = "Shift" in event.modifiers
                    self.tracks_viewer.selected_nodes.add(node_id, append)

        # Listen to paint events and undo/redo requests
        self.events.paint.connect(self._on_paint)
        self.tracks_viewer.undo_seg.connect(self._undo)
        self.tracks_viewer.redo_seg.connect(self._redo)

    def _redo(self):
        """Call the original undo functionality of the labels layer"""

        self._load_history(self._redo_history, self._undo_history, undoing=False)

    def redo(self):
        """Overwrite the redo functionality of the labels layer and invoke redo action on the tracks_viewer.tracks_controller first"""

        controller = self.tracks_viewer.tracks_controller
        if controller.last_action < len(controller.actions) - 1:
            action_to_redo = controller.actions[controller.last_action + 1]
            self.tracks_viewer.tracks_controller.last_action += 1
            action_to_redo.apply()
            self.tracks_viewer.tracks.refresh()
            if (
                action_to_redo.update_seg
            ):  # only redo segmentation if this action involved a segmentation update
                self._redo()

    def _undo(self):
        """Call the original undo functionality of the labels layer"""

        self._load_history(self._undo_history, self._redo_history, undoing=True)

    def undo(self):
        """Overwrite undo function and invoke undo action on the tracks_viewer.tracks_controller"""

        controller = self.tracks_viewer.tracks_controller
        action_to_undo = controller.actions[controller.last_action]
        self.tracks_viewer.tracks_controller.last_action -= 1
        inverse_action = action_to_undo.inverse()
        inverse_action.apply()
        self.tracks_viewer.tracks.refresh()
        if (
            action_to_undo.update_seg
        ):  # only undo segmentation if this action involved a segmentation update
            self._undo()  # call the original undo function

    def _on_paint(self, event):
        """Listen to the paint event and check which track_ids have changed"""

        old_values = list(np.unique(np.concatenate([ev[1] for ev in event.value])))
        new_value = [event.value[-1][-1]]

        # check which time points are affected (user might paint in 3 dimensions on 2D + time data)
        time_points = list(
            np.unique(np.concatenate([ev[0][0] for ev in event.value]))
        )  # have to check the first array axis of the first element (the array) of all elements in event.value (just the last one is not always sufficient)

        changed_track_ids = old_values + new_value
        changed_track_ids = [value for value in changed_track_ids if value != 0]

        current_timepoint = self.viewer.dims.current_step[
            0
        ]  # also pass on the current time point to know which node to select later

        self.tracks_viewer.tracks_controller.update_segmentations(
            time_points, current_timepoint, changed_track_ids
        )

    def _refresh(self):
        """Refresh the data in the labels layer"""

        self.data = np.squeeze(self.tracks_viewer.tracks.segmentation)
        self.nodes = list(self.tracks_viewer.tracks.graph.nodes)

        self.node_properties = {
            "node_id": self.nodes,
            "track_id": [
                data[NodeAttr.TRACK_ID.value]
                for _, data in self.tracks_viewer.tracks.graph.nodes(data=True)
            ],
            "t": [self.tracks_viewer.tracks.get_time(node) for node in self.nodes],
        }

        self.refresh()

    def update_label_colormap(self, visible: list[int] | str) -> None:
        """Updates the opacity of the label colormap to highlight the selected label
        and optionally hide cells not belonging to the current lineage"""

        highlighted = [
            self.tracks_viewer.tracks.graph.nodes[node][NodeAttr.TRACK_ID.value]
            for node in self.tracks_viewer.selected_nodes
            if self.tracks_viewer.tracks.get_time(node)
            == self.viewer.dims.current_step[0]
        ]

        if len(highlighted) > 0:
            self.selected_label = highlighted[
                0
            ]  # set the first track_id to be the selected label color

        # update the opacity of the cyclic label colormap values according to whether nodes are visible/invisible/highlighted
        if visible == "all":
            self.colormap.colors[:, -1] = (
                0.6  # set opacity of all labels everything to 0.6
            )

        else:
            self.colormap.colors[:, -1] = (
                0  # set opacity of all labels everything to 0 and replace by 0.6 for visible labels
            )
            for label in visible:
                # find the index in the cyclic label colormap
                matches = np.all(
                    self.colormap.colors[:, :3] == self.colormap.map(label)[:3], axis=1
                )
                if np.any(matches):
                    index = np.argmax(matches)
                    self.colormap.colors[index][-1] = 0.6

        for label in highlighted:
            matches = np.all(
                self.colormap.colors[:, :3] == self.colormap.map(label)[:3], axis=1
            )
            if np.any(matches):
                index = np.argmax(matches)
                self.colormap.colors[index][-1] = 1  # full opacity

        self.colormap = CyclicLabelColormap(
            colors=self.colormap.colors
        )  # create a new colormap from the updated colors (otherwise it does not refresh)

    def new_colormap(self):
        """Extended version of existing function, to emit refresh signal to also update colors in other layers/widgets"""

        super().new_colormap()
        self.tracks_viewer.colormap = self.colormap
        self.tracks_viewer._refresh()
