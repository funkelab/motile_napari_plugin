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

        nodes = list(tracks.graph.nodes)
        points = [tracks.get_location(node, incl_time=True) for node in nodes]
        colors = [
            colormap.map(tracks.graph.nodes[node]["tracklet_id"])
            for node in nodes
        ]
        symbols = self.get_symbols(tracks, symbolmap)

        super().__init__(
            data=points,
            name=name,
            symbol=symbols,
            face_color=colors,
            size=5,
            # properties=data, TODO
            border_color=[1, 1, 1, 1],
        )

        self.viewer = viewer
        self.selected_nodes = selected_nodes

        @self.mouse_drag_callbacks.append
        def click(layer, event):
            if event.type == "mouse_press":
                point_index = layer.get_value(
                    event.position,
                    view_direction=event.view_direction,
                    dims_displayed=event.dims_displayed,
                    world=True,
                )
                if point_index is not None:
                    node_id = layer.properties["node_id"][point_index]
                    index = [
                        i
                        for i, nid in enumerate(layer.properties["node_id"])
                        if nid == node_id
                    ][0]
                    node = {
                        key: value[index]
                        for key, value in layer.properties.items()
                    }

                    if len(node) > 0:
                        append = "Shift" in event.modifiers
                        self.selected_nodes.append(node, append)

    def get_symbols(
        self, tracks: Tracks, symbolmap: dict[NodeType, str]
    ) -> list[str]:
        statemap = {
            0: NodeType.END,
            1: NodeType.CONTINUE,
            2: NodeType.SPLIT,
        }
        symbols = [
            symbolmap[statemap[degree]]
            for _, degree in tracks.graph.out_degree
        ]
        return symbols

    def update_point_outline(self, visible: list[int] | str) -> None:
        """Update the outline color of the selected points and visibility according to display mode"""

        if visible == "all":
            self.shown[:] = True
        else:
            indices = np.where(np.isin(self.properties["track_id"], visible))[
                0
            ].tolist()
            self.shown[:] = False
            self.shown[indices] = True

        self.border_color = [1, 1, 1, 1]
        for node in self.selected_nodes:
            self.border_color[node["index"]] = (
                0,
                1,
                1,
                1,
            )
        self.refresh()
