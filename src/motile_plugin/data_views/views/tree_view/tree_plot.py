# do not put the from __future__ import annotations as it breaks the injection
from typing import Any

import numpy as np
import pandas as pd
import pyqtgraph as pg
from psygnal import Signal
from pyqtgraph.Qt import QtCore
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from vispy import scene


class CustomViewBox(pg.ViewBox):
    selected_rect = Signal(Any)

    def __init__(self, *args, **kwds):
        kwds["enableMenu"] = False
        pg.ViewBox.__init__(self, *args, **kwds)
        # self.setMouseMode(self.RectMode)

    ## reimplement right-click to zoom out
    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.RightButton:
            self.autoRange()

    def showAxRect(self, ax, **kwargs):
        """Set the visible range to the given rectangle
        Emits sigRangeChangedManually without changing the range.
        """
        # Emit the signal without setting the range
        self.sigRangeChangedManually.emit(self.state["mouseEnabled"])

    def mouseDragEvent(self, ev, axis=None):
        """Modified mouseDragEvent function to check which mouse mode to use
        and to submit rectangle coordinates for selecting multiple nodes if necessary"""

        super().mouseDragEvent(ev, axis)

        # use RectMode when pressing shift
        if ev.modifiers() == QtCore.Qt.ShiftModifier:
            self.setMouseMode(self.RectMode)

            if ev.isStart():
                self.mouse_start_pos = self.mapSceneToView(ev.scenePos())
            elif ev.isFinish():
                rect_end_pos = self.mapSceneToView(ev.scenePos())
                rect = QtCore.QRectF(self.mouse_start_pos, rect_end_pos).normalized()
                self.selected_rect.emit(rect)  # emit the rectangle
                ev.accept()
            else:
                ev.ignore()
        else:
            # Otherwise, set pan mode
            self.setMouseMode(self.PanMode)


class TreePlot(QWidget):
    node_clicked = Signal(Any, bool)  # node_id, append
    nodes_selected = Signal(list, bool)

    def __init__(self, parent=None):
        """Construct the pyqtgraph treewidget. This is the actual canvas
        on which the tree view is drawn.
        """
        super().__init__(parent=parent)

        self.setFocusPolicy(Qt.StrongFocus)
        layout = QVBoxLayout(self)

        # self.setTitle("Lineage Tree")

        self._pos = []
        self.adj = []
        self.symbolBrush = []
        self.symbols = []
        self.pen = []
        self.outline_pen = []
        self.node_ids = []
        self.sizes = []

        self.view_direction = None
        self.feature = None
        self.canvas = scene.SceneCanvas(keys="interactive", size=(800, 600), show=True)
        self.view = self.canvas.central_widget.add_view()
        self.canvas.events.mouse_press.connect(self._on_click)
        camera = scene.cameras.PanZoomCamera(
            parent=self.view.scene, aspect=1, name="PanZoom"
        )
        self.view.camera = camera
        layout.addWidget(self.canvas.native)
        # self.set_view("vertical", feature="tree")
        # self.getViewBox().selected_rect.connect(self.select_points_in_rect)

    def draw_graph(self, node_pos, edge_pos):
        if len(node_pos) == 0:
            return
        node_pos = np.array(node_pos)
        edge_pos = np.array(edge_pos)
        print(f"Node Pos Shape: {node_pos.shape}")

        print(f"Edge Pos Shape: {edge_pos.shape}")
        print(edge_pos[1:10])
        node_markers = scene.visuals.Markers(
            pos=node_pos, size=10.0, scaling="scene", spherical=False
        )
        # node_markers.parent = self.view.scene
        self.view.add(node_markers)

        edge_lines = scene.visuals.Line(pos=edge_pos, width=5.0, connect="segments")
        # edge_lines.parent = self.view.scene
        self.view.add(edge_lines)

    def select_points_in_rect(self, rect: QtCore.QRectF):
        """Select all nodes in given rectangle"""
        # scatter_data = self.g.scatter.data
        # x = scatter_data["x"]
        # y = scatter_data["y"]
        # data = scatter_data["data"]

        # # Filter points that are within the rectangle
        # points_within_rect = [
        #     (x[i], y[i], data[i]) for i in range(len(x)) if rect.contains(x[i], y[i])
        # ]
        # selected_nodes = [point[2] for point in points_within_rect]
        # self.nodes_selected.emit(selected_nodes, True)

    def update(
        self,
        track_df: pd.DataFrame,
        view_direction: str,
        feature: str,
        selected_nodes: list[Any],
        reset_view: bool | None = False,
    ):
        """Update the entire view, including the data, view direction, and
        selected nodes

        Args:
            track_df (pd.DataFrame): The dataframe containing the graph data
            view_direction (str): The view direction
            feature (str): The feature to be plotted ('tree' or 'area')
            selected_nodes (list[Any]): The currently selected nodes to be highlighted
        """
        self.set_data(track_df, feature)
        self._update_viewed_data(view_direction)  # this can be expensive
        # self.set_view(view_direction, feature, reset_view)
        # self.set_selection(selected_nodes, feature)

    def set_view(
        self, view_direction: str, feature: str, reset_view: bool | None = False
    ):
        """Set the view direction, saving the new value as an attribute and
        changing the axes labels. Shortcuts if the view direction is already
        correct. Does not actually update the rendered graph (need to call
        _update_viewed_data).

        Args:
            view_direction (str): "horizontal" or "vertical"
            feature (str): the feature being displayed, it can be 'tree' or 'area'
        """
        # if view_direction == self.view_direction and feature == self.feature:
        #     if view_direction == "horizontal" or reset_view:
        #         self.autoRange()
        #     return
        # if view_direction == "vertical":
        #     self.setLabel("left", text="Time Point")
        #     self.getAxis("left").setStyle(showValues=True)
        #     if feature == "tree":
        #         self.getAxis("bottom").setStyle(showValues=False)
        #         self.setLabel("bottom", text="")
        #     else:  # should this actually ever happen?
        #         self.getAxis("bottom").setStyle(showValues=True)
        #         self.setLabel("bottom", text="Object size in calibrated units")
        #         self.autoRange()
        #     self.invertY(True)  # to show tracks from top to bottom
        # elif view_direction == "horizontal":
        #     self.setLabel("bottom", text="Time Point")
        #     self.getAxis("bottom").setStyle(showValues=True)
        #     if feature == "tree":
        #         self.setLabel("left", text="")
        #         self.getAxis("left").setStyle(showValues=False)
        #     else:
        #         self.setLabel("left", text="Object size in calibrated units")
        #         self.getAxis("left").setStyle(showValues=True)
        #         self.autoRange()
        #     self.invertY(False)
        # if (
        #     self.view_direction != view_direction
        #     or self.feature != feature
        #     or reset_view
        # ):
        #     self.autoRange()
        # self.view_direction = view_direction
        # self.feature = feature

    def _on_click(self, event) -> None:
        """Adds the selected point to the selected_nodes list. Called when
        the user clicks on the TreeWidget to select nodes.

        Args:
            points (np.ndarray): _description_
            ev (some sort of VispyEvent): _description_
        """
        # print(f"{event.pos=}")
        # transform = self.view.camera.transforms.get_transform(map_to="canvas")
        # data_pos = transform.imap(event.pos)[0:2]  # ignore z
        # print(f"{data_pos=}")
        data_x, data_y = event.pos
        self.track_df["temp_dist"] = (self.track_df["x"] - data_x) ** 2 + (
            self.track_df["y"] > data_y
        ) ** 2
        closest_node = self.track_df.iloc[self.track_df["temp_dist"].idxmin()]
        print(closest_node)

        tolerance = 5
        if closest_node["temp_dist"] < tolerance:
            node_id = closest_node["node_id"]
        else:
            node_id = None
        print(node_id)
        self.track_df.drop(columns=["temp_dist"])
        # modifiers = ev.modifiers()
        # node_id = points[0].data()
        # append = Qt.ShiftModifier == modifiers
        # self.node_clicked.emit(node_id, append)

    def set_data(self, track_df: pd.DataFrame, feature: str) -> None:
        """Updates the stored pyqtgraph content based on the given dataframe.
        Does not render the new information (need to call _update_viewed_data).

        Args:
            track_df (pd.DataFrame): The tracks df to compute the pyqtgraph
                content for. Can be all lineages or any subset of them.
            feature (str): The feature to be plotted. Can either be 'tree', or 'area'.
        """
        self.track_df = track_df
        self._create_pyqtgraph_content(track_df, feature)

    def _update_viewed_data(self, view_direction: str):
        """Set the data according to the view direction
        Args:
            view_direction (str): direction to plot the data, either 'horizontal' or 'vertical'
        """
        if len(self._pos) == 0 or view_direction == "vertical":
            pos_data = self._pos
        else:
            pos_data = np.flip(self._pos, axis=1)

        self.draw_graph(pos_data, self.adj)

    def _create_pyqtgraph_content(self, track_df: pd.DataFrame, feature: str) -> None:
        """Parse the given track_df into the format that pyqtgraph expects
        and save the information as attributes.

        Args:
            track_df (pd.DataFrame): The dataframe containing the graph to be
                rendered in the tree view. Can be all lineages or a subset.
            feature (str): The feature to be plotted. Can either be 'tree' or 'area'.
        """
        self._pos = []
        self.adj = []
        self.symbols = []
        self.symbolBrush = []
        self.pen = []
        self.sizes = []
        self.node_ids = []

        if track_df is not None and not track_df.empty:
            self.symbols = track_df["symbol"].to_list()
            self.symbolBrush = track_df["color"].to_numpy()
            if feature == "tree":
                self._pos = track_df[["x_axis_pos", "t"]].to_numpy()
            elif feature == "area":
                self._pos = track_df[["area", "t"]].to_numpy()
            self.node_ids = track_df["node_id"].to_list()
            self.sizes = np.array(
                [
                    8,
                ]
                * len(self.symbols)
            )

            valid_edges_df = track_df[track_df["parent_id"] != 0]
            node_ids_to_pos = {
                node_id: self._pos[index] for index, node_id in enumerate(self.node_ids)
            }
            edges_df = valid_edges_df[["node_id", "parent_id"]]
            self.pen = valid_edges_df["color"].to_numpy()
            edges_df_mapped = edges_df.map(lambda _id: node_ids_to_pos[_id])
            # breakpoint()
            self.adj = np.vstack(edges_df_mapped.values.flatten())

        self.outline_pen = np.array(
            [pg.mkPen(QColor(150, 150, 150)) for i in range(len(self._pos))]
        )

    def set_selection(self, selected_nodes: list[Any], feature: str) -> None:
        """Set the provided list of nodes to be selected. Increases the size
        and highlights the outline with blue. Also centers the view
        if the first selected node is not visible in the current canvas.

        Args:
            selected_nodes (list[Any]): A list of node ids to be selected.
            feature (str): the feature that is being plotted, either 'tree' or 'area'
        """

        # # reset to default size and color to avoid problems with the array lengths
        # self.g.scatter.setPen(pg.mkPen(QColor(150, 150, 150)))
        # self.g.scatter.setSize(10)

        # size = (
        #     self.sizes.copy()
        # )  # just copy the size here to keep the original self.sizes intact

        # outlines = self.outline_pen.copy()
        # axis_label = (
        #     "area" if feature == "area" else "x_axis_pos"
        # )  # check what is currently being shown, to know how to scale  the view

        # if len(selected_nodes) > 0:
        #     x_values = []
        #     t_values = []
        #     for node_id in selected_nodes:
        #         node_df = self.track_df.loc[self.track_df["node_id"] == node_id]
        #         if not node_df.empty:
        #             x_axis_value = node_df[axis_label].values[0]
        #             t = node_df["t"].values[0]

        #             x_values.append(x_axis_value)
        #             t_values.append(t)

        #             # Update size and outline
        #             index = self.node_ids.index(node_id)
        #             size[index] += 5
        #             outlines[index] = pg.mkPen(color="c", width=2)

        #     # Center point if a single node is selected, center range if multiple nodes are selected
        #     if len(selected_nodes) == 1:
        #         self._center_view(x_axis_value, t)
        #     else:
        #         min_x = np.min(x_values)
        #         max_x = np.max(x_values)
        #         min_t = np.min(t_values)
        #         max_t = np.max(t_values)
        #         self._center_range(min_x, max_x, min_t, max_t)

        # self.g.scatter.setPen(outlines)
        # self.g.scatter.setSize(size)

    def _center_range(self, min_x: int, max_x: int, min_t: int, max_t: int):
        """Check whether viewbox contains current range and adjust if not"""
        # if self.view_direction == "horizontal":
        #     min_x, max_x, min_t, max_t = min_t, max_t, min_x, max_x

        # view_box = self.plotItem.getViewBox()
        # current_range = view_box.viewRange()

        # x_range = current_range[0]
        # y_range = current_range[1]

        # # Check if the new range is within the current range
        # if (
        #     x_range[0] <= min_x
        #     and x_range[1] >= max_x
        #     and y_range[0] <= min_t
        #     and y_range[1] >= max_t
        # ):
        #     return
        # else:
        #     view_box.setRange(xRange=(min_x, max_x), yRange=(min_t, max_t))

    def _center_view(self, center_x: int, center_y: int):
        """Center the Viewbox on given coordinates"""

        # if self.view_direction == "horizontal":
        #     center_x, center_y = (
        #         center_y,
        #         center_x,
        #     )  # flip because the axes have changed in horizontal mode

        # view_box = self.plotItem.getViewBox()
        # current_range = view_box.viewRange()

        # x_range = current_range[0]
        # y_range = current_range[1]

        # # Check if the new center is within the current range
        # if (
        #     x_range[0] <= center_x <= x_range[1]
        #     and y_range[0] <= center_y <= y_range[1]
        # ):
        #     return

        # # Calculate the width and height of the current view
        # current_width = x_range[1] - x_range[0]
        # current_height = y_range[1] - y_range[0]

        # # Calculate new ranges maintaining the current width and height
        # new_x_range = (
        #     center_x - current_width / 2,
        #     center_x + current_width / 2,
        # )
        # new_y_range = (
        #     center_y - current_height / 2,
        #     center_y + current_height / 2,
        # )

        # view_box.setRange(xRange=new_x_range, yRange=new_y_range, padding=0)
