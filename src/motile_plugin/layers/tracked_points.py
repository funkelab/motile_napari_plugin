import napari
import numpy as np
import pandas as pd

from ..utils.node_selection import NodeSelectionList


class TrackPoints(napari.layers.Points):
    """Extended points layer that holds the track information and emits and responds to dynamics visualization signals"""

    def __init__(
        self,
        viewer: napari.Viewer,
        data: pd.DataFrame,
        name: str,
        selected_nodes: NodeSelectionList,
    ):

        # Collect point data, colors and symbols directly from the track_data dataframe
        colors = np.array(data["color"].tolist()) / 255
        annotate_indices = data[
            data["annotated"]
        ].index  # manual edits should be displayed in a different color
        colors[annotate_indices] = np.array([1, 0, 0, 1])
        symbols = np.array(data["symbol"].tolist())

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

        super().__init__(
            data=points,
            name=name,
            symbol=symbols,
            face_color=colors,
            size=5,
            properties=data,
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
