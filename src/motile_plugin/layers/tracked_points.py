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
        scale: np.array,
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
            blending="translucent",
            scale=scale,
        )

        self.viewer = viewer
        self.selected_nodes = selected_nodes
        self.visible_nodes = "all"
        self.plane_nodes = "all"

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

    def update_point_outline(
        self,
        visible_nodes: list[int] | str | None = None,
        plane_nodes: list[int] | str | None = None,
    ) -> None:
        """Update the outline color of the selected points and visibility according to display mode"""

        if visible_nodes is not None:
            self.visible_nodes = visible_nodes

        if plane_nodes is not None:
            self.plane_nodes = plane_nodes

        if isinstance(self.visible_nodes, str) and isinstance(
            self.plane_nodes, str
        ):
            visible = "all"
        elif not isinstance(self.visible_nodes, str) and isinstance(
            self.plane_nodes, str
        ):
            visible = self.visible_nodes
        elif isinstance(self.visible_nodes, str) and not isinstance(
            self.plane_nodes, str
        ):
            visible = self.plane_nodes
        else:
            visible = list(
                set(self.visible_nodes).intersection(set(self.plane_nodes))
            )

        if isinstance(visible, str):
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
