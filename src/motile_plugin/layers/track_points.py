import napari
import numpy as np

from motile_plugin.core import NodeType, Tracks

from ..utils.node_selection import NodeSelectionList


class TrackPoints(napari.layers.Points):
    """Extended points layer that holds the track information and emits and responds to dynamics visualization signals"""

    def __init__(
        self,
        viewer: napari.Viewer,
        tracks: Tracks,
        name: str,
        selected_nodes: NodeSelectionList,
        symbolmap: dict[NodeType, str],
        colormap: napari.utils.Colormap,
    ):
        self.colormap = colormap
        self.symbolmap = symbolmap

        self.nodes = list(tracks.graph.nodes)
        self.node_index_dict = dict(
            zip(
                self.nodes,
                [self.nodes.index(node) for node in self.nodes],
                strict=False,
            )
        )
        points = [tracks.get_location(node, incl_time=True) for node in self.nodes]
        track_ids = [tracks.graph.nodes[node]["tracklet_id"] for node in self.nodes]
        colors = [colormap.map(track_id) for track_id in track_ids]
        symbols = self.get_symbols(tracks, symbolmap)

        super().__init__(
            data=points,
            name=name,
            symbol=symbols,
            face_color=colors,
            size=5,
            properties={"node_id": self.nodes, "track_id": track_ids},
            border_color=[1, 1, 1, 1],
        )

        self.viewer = viewer
        self.selected_nodes = selected_nodes

        @self.mouse_drag_callbacks.append
        def click(layer, event):
            if event.type == "mouse_press":
                # is the value passed from the click event?
                point_index = layer.get_value(
                    event.position,
                    view_direction=event.view_direction,
                    dims_displayed=event.dims_displayed,
                    world=True,
                )
                if point_index is not None:
                    node_id = self.nodes[point_index]
                    append = "Shift" in event.modifiers
                    self.selected_nodes.add(node_id, append)

        # listen to updates in the selected data (from the point selection tool) to update the nodes in self.selected_nodes
        self.selected_data.events.items_changed.connect(self._update_selection)

    def _update_selection(self):
        """Replaces the list of selected_nodes with the selection provided by the user"""

        selected_points = self.selected_data
        self.selected_nodes.reset()
        for point in selected_points:
            node_id = self.nodes[point]
            self.selected_nodes.add(node_id, True)

    def get_symbols(self, tracks: Tracks, symbolmap: dict[NodeType, str]) -> list[str]:
        statemap = {
            0: NodeType.END,
            1: NodeType.CONTINUE,
            2: NodeType.SPLIT,
        }
        symbols = [symbolmap[statemap[degree]] for _, degree in tracks.graph.out_degree]
        return symbols

    def update_point_outline(self, visible: list[int] | str) -> None:
        """Update the outline color of the selected points and visibility according to display mode

        Args:
            visible (list[int] | str): A list of track ids, or "all"
        """
        # filter out the non-selected tracks if in lineage mode
        if visible == "all":
            self.shown[:] = True
        else:
            indices = np.where(np.isin(self.properties["track_id"], visible))[
                0
            ].tolist()
            self.shown[:] = False
            self.shown[indices] = True

        # set border color for selected item
        self.border_color = [1, 1, 1, 1]
        self.size = 5
        for node in self.selected_nodes:
            index = self.node_index_dict[node]
            self.border_color[index] = (
                0,
                1,
                1,
                1,
            )
            self.size[index] = 7
        self.refresh()
