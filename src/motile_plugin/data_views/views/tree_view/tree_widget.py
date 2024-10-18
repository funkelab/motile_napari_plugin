# do not put the from __future__ import annotations as it breaks the injection

from typing import Any

import napari
import numpy as np
import pandas as pd
import pyqtgraph as pg
from psygnal import Signal
from pyqtgraph.Qt import QtCore
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QKeyEvent, QMouseEvent
from qtpy.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible

from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer

from .navigation_widget import NavigationWidget
from .tree_view_feature_widget import TreeViewFeatureWidget
from .tree_view_mode_widget import TreeViewModeWidget
from .tree_widget_utils import (
    extract_lineage_tree,
    extract_sorted_tracks,
)


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


class TreePlot(pg.PlotWidget):
    node_clicked = Signal(Any, bool)  # node_id, append
    nodes_selected = Signal(list, bool)

    def __init__(self) -> pg.PlotWidget:
        """Construct the pyqtgraph treewidget. This is the actual canvas
        on which the tree view is drawn.
        """
        super().__init__(viewBox=CustomViewBox())

        self.setFocusPolicy(Qt.StrongFocus)
        self.setTitle("Lineage Tree")

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
        self.g = pg.GraphItem()
        self.g.scatter.sigClicked.connect(self._on_click)
        self.addItem(self.g)
        self.set_view("vertical", feature="tree")
        self.getViewBox().selected_rect.connect(self.select_points_in_rect)

    def select_points_in_rect(self, rect: QtCore.QRectF):
        """Select all nodes in given rectangle"""

        scatter_data = self.g.scatter.data
        x = scatter_data["x"]
        y = scatter_data["y"]
        data = scatter_data["data"]

        # Filter points that are within the rectangle
        points_within_rect = [
            (x[i], y[i], data[i]) for i in range(len(x)) if rect.contains(x[i], y[i])
        ]
        selected_nodes = [point[2] for point in points_within_rect]
        self.nodes_selected.emit(selected_nodes, True)

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
        self.set_view(view_direction, feature, reset_view)
        self.set_selection(selected_nodes, feature)

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

        if view_direction == self.view_direction and feature == self.feature:
            if view_direction == "horizontal" or reset_view:
                self.autoRange()
            return
        if view_direction == "vertical":
            self.setLabel("left", text="Time Point")
            self.getAxis("left").setStyle(showValues=True)
            if feature == "tree":
                self.getAxis("bottom").setStyle(showValues=False)
                self.setLabel("bottom", text="")
            else:  # should this actually ever happen?
                self.getAxis("bottom").setStyle(showValues=True)
                self.setLabel("bottom", text="Object size in calibrated units")
                self.autoRange()
            self.invertY(True)  # to show tracks from top to bottom
        elif view_direction == "horizontal":
            self.setLabel("bottom", text="Time Point")
            self.getAxis("bottom").setStyle(showValues=True)
            if feature == "tree":
                self.setLabel("left", text="")
                self.getAxis("left").setStyle(showValues=False)
            else:
                self.setLabel("left", text="Object size in calibrated units")
                self.getAxis("left").setStyle(showValues=True)
                self.autoRange()
            self.invertY(False)
        if (
            self.view_direction != view_direction
            or self.feature != feature
            or reset_view
        ):
            self.autoRange()
        self.view_direction = view_direction
        self.feature = feature

    def _on_click(self, _, points: np.ndarray, ev: QMouseEvent) -> None:
        """Adds the selected point to the selected_nodes list. Called when
        the user clicks on the TreeWidget to select nodes.

        Args:
            points (np.ndarray): _description_
            ev (QMouseEvent): _description_
        """

        modifiers = ev.modifiers()
        node_id = points[0].data()
        append = Qt.ShiftModifier == modifiers
        self.node_clicked.emit(node_id, append)

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
        self.g.scatter.setPen(
            pg.mkPen(QColor(150, 150, 150))
        )  # first reset the pen to avoid problems with length mismatch between the different properties
        self.g.scatter.setSize(10)
        if len(self._pos) == 0 or view_direction == "vertical":
            pos_data = self._pos
        else:
            pos_data = np.flip(self._pos, axis=1)

        self.g.setData(
            pos=pos_data,
            adj=self.adj,
            symbol=self.symbols,
            symbolBrush=self.symbolBrush,
            pen=self.pen,
            data=self.node_ids,
        )
        self.g.scatter.setPen(self.outline_pen)
        self.g.scatter.setSize(self.sizes)

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
            node_ids_to_index = {
                node_id: index for index, node_id in enumerate(self.node_ids)
            }
            edges_df = valid_edges_df[["node_id", "parent_id"]]
            self.pen = valid_edges_df["color"].to_numpy()
            edges_df_mapped = edges_df.map(lambda _id: node_ids_to_index[_id])
            self.adj = edges_df_mapped.to_numpy()

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

        # reset to default size and color to avoid problems with the array lengths
        self.g.scatter.setPen(pg.mkPen(QColor(150, 150, 150)))
        self.g.scatter.setSize(10)

        size = (
            self.sizes.copy()
        )  # just copy the size here to keep the original self.sizes intact

        outlines = self.outline_pen.copy()
        axis_label = (
            "area" if feature == "area" else "x_axis_pos"
        )  # check what is currently being shown, to know how to scale  the view

        if len(selected_nodes) > 0:
            x_values = []
            t_values = []
            for node_id in selected_nodes:
                node_df = self.track_df.loc[self.track_df["node_id"] == node_id]
                if not node_df.empty:
                    x_axis_value = node_df[axis_label].values[0]
                    t = node_df["t"].values[0]

                    x_values.append(x_axis_value)
                    t_values.append(t)

                    # Update size and outline
                    index = self.node_ids.index(node_id)
                    size[index] += 5
                    outlines[index] = pg.mkPen(color="c", width=2)

            # Center point if a single node is selected, center range if multiple nodes are selected
            if len(selected_nodes) == 1:
                self._center_view(x_axis_value, t)
            else:
                min_x = np.min(x_values)
                max_x = np.max(x_values)
                min_t = np.min(t_values)
                max_t = np.max(t_values)
                self._center_range(min_x, max_x, min_t, max_t)

        self.g.scatter.setPen(outlines)
        self.g.scatter.setSize(size)

    def _center_range(self, min_x: int, max_x: int, min_t: int, max_t: int):
        """Check whether viewbox contains current range and adjust if not"""

        if self.view_direction == "horizontal":
            min_x, max_x, min_t, max_t = min_t, max_t, min_x, max_x

        view_box = self.plotItem.getViewBox()
        current_range = view_box.viewRange()

        x_range = current_range[0]
        y_range = current_range[1]

        # Check if the new range is within the current range
        if (
            x_range[0] <= min_x
            and x_range[1] >= max_x
            and y_range[0] <= min_t
            and y_range[1] >= max_t
        ):
            return
        else:
            view_box.setRange(xRange=(min_x, max_x), yRange=(min_t, max_t))

    def _center_view(self, center_x: int, center_y: int):
        """Center the Viewbox on given coordinates"""

        if self.view_direction == "horizontal":
            center_x, center_y = (
                center_y,
                center_x,
            )  # flip because the axes have changed in horizontal mode

        view_box = self.plotItem.getViewBox()
        current_range = view_box.viewRange()

        x_range = current_range[0]
        y_range = current_range[1]

        # Check if the new center is within the current range
        if (
            x_range[0] <= center_x <= x_range[1]
            and y_range[0] <= center_y <= y_range[1]
        ):
            return

        # Calculate the width and height of the current view
        current_width = x_range[1] - x_range[0]
        current_height = y_range[1] - y_range[0]

        # Calculate new ranges maintaining the current width and height
        new_x_range = (
            center_x - current_width / 2,
            center_x + current_width / 2,
        )
        new_y_range = (
            center_y - current_height / 2,
            center_y + current_height / 2,
        )

        view_box.setRange(xRange=new_x_range, yRange=new_y_range, padding=0)


class TreeWidget(QWidget):
    """pyqtgraph-based widget for lineage tree visualization and navigation"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.track_df = pd.DataFrame()  # all tracks
        self.lineage_df = pd.DataFrame()  # the currently viewed subset of lineages
        self.graph = None
        self.mode = "all"  # options: "all", "lineage"
        self.feature = "tree"  # options: "tree", "area"
        self.view_direction = "vertical"  # options: "horizontal", "vertical"

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.selected_nodes = self.tracks_viewer.selected_nodes
        self.selected_nodes.list_updated.connect(self._update_selected)
        self.tracks_viewer.tracks_updated.connect(self._update_track_data)

        # Construct the tree view pyqtgraph widget
        layout = QVBoxLayout()

        self.tree_widget: TreePlot = TreePlot()
        self.tree_widget.node_clicked.connect(self.selected_nodes.add)
        self.tree_widget.nodes_selected.connect(self.selected_nodes.add_list)

        # Add radiobuttons for switching between different display modes
        self.mode_widget = TreeViewModeWidget()
        self.mode_widget.change_mode.connect(self._set_mode)

        # Add buttons to change which feature to display
        self.feature_widget = TreeViewFeatureWidget()
        self.feature_widget.change_feature.connect(self._set_feature)

        # Add navigation widget
        self.navigation_widget = NavigationWidget(
            self.track_df,
            self.lineage_df,
            self.view_direction,
            self.selected_nodes,
            self.feature,
        )

        # Construct a toolbar and set main layout
        panel_layout = QHBoxLayout()
        panel_layout.addWidget(self.mode_widget)
        panel_layout.addWidget(self.feature_widget)
        panel_layout.addWidget(self.navigation_widget)
        panel_layout.setSpacing(0)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        panel.setLayout(panel_layout)
        panel.setMaximumWidth(820)
        panel.setMaximumHeight(78)

        # Make a collapsible for TreeView widgets
        collapsable_widget = QCollapsible("Show/Hide Tree View Controls")
        collapsable_widget.layout().setContentsMargins(0, 0, 0, 0)
        collapsable_widget.layout().setSpacing(0)
        collapsable_widget.addWidget(panel)
        collapsable_widget.collapse(animate=False)

        layout.addWidget(collapsable_widget)
        layout.addWidget(self.tree_widget)
        layout.setSpacing(0)
        self.setLayout(layout)
        self._update_track_data(reset_view=True)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        key_map = {
            Qt.Key_Delete: self.delete_node,
            Qt.Key_D: self.delete_node,
            Qt.Key_A: self.create_edge,
            Qt.Key_B: self.delete_edge,
            Qt.Key_Z: self.undo,
            Qt.Key_R: self.redo,
            Qt.Key_Q: self.toggle_display_mode,
            Qt.Key_W: self.toggle_feature_mode,
            Qt.Key_X: lambda: self.set_mouse_enabled(x=True, y=False),
            Qt.Key_Y: lambda: self.set_mouse_enabled(x=False, y=True),
        }

        # Check if the key has a handler in the map
        handler = key_map.get(event.key())

        if handler:
            handler()  # Call the function bound to the key
        else:
            # Handle navigation (Arrow keys)
            direction_map = {
                Qt.Key_Left: "left",
                Qt.Key_Right: "right",
                Qt.Key_Up: "up",
                Qt.Key_Down: "down",
            }
            direction = direction_map.get(event.key())
            if direction:
                self.navigation_widget.move(direction)

    def delete_node(self):
        """Delete a node."""
        self.tracks_viewer.delete_node()

    def create_edge(self):
        """Create an edge."""
        self.tracks_viewer.create_edge()

    def delete_edge(self):
        """Delete an edge."""
        self.tracks_viewer.delete_edge()

    def undo(self):
        """Undo action."""
        self.tracks_viewer.undo()

    def redo(self):
        """Redo action."""
        self.tracks_viewer.redo()

    def toggle_display_mode(self):
        """Toggle display mode."""
        self.mode_widget._toggle_display_mode()

    def toggle_feature_mode(self):
        """Toggle feature mode."""
        self.feature_widget._toggle_feature_mode()

    def set_mouse_enabled(self, x: bool, y: bool):
        """Enable or disable mouse zoom scrolling in X or Y direction."""
        self.tree_widget.setMouseEnabled(x=x, y=y)

    def keyReleaseEvent(self, ev):
        """Reset the mouse scrolling when releasing the X/Y key"""

        if ev.key() == Qt.Key_X or ev.key() == Qt.Key_Y:
            self.tree_widget.setMouseEnabled(x=True, y=True)

    def _update_selected(self):
        """Called whenever the selection list is updated. Only re-computes
        the full graph information when the new selection is not in the
        lineage df (and in lineage mode)
        """

        if self.mode == "lineage" and any(
            node not in np.unique(self.lineage_df["node_id"].values)
            for node in self.selected_nodes
        ):
            self._update_lineage_df()
            self.tree_widget.update(
                self.lineage_df,
                self.view_direction,
                self.feature,
                self.selected_nodes,
            )
        else:
            self.tree_widget.set_selection(self.selected_nodes, self.feature)

    def _update_track_data(self, reset_view: bool | None = None) -> None:
        """Called when the TracksViewer emits the tracks_updated signal, indicating
        that a new set of tracks should be viewed.
        """

        if self.tracks_viewer.tracks is None:
            self.track_df = pd.DataFrame()
            self.graph = None
        else:
            if reset_view:
                self.track_df = extract_sorted_tracks(
                    self.tracks_viewer.tracks, self.tracks_viewer.colormap
                )
            else:
                self.track_df = extract_sorted_tracks(
                    self.tracks_viewer.tracks,
                    self.tracks_viewer.colormap,
                    self.track_df,
                )
            self.graph = self.tracks_viewer.tracks.graph

        # check whether we have area measurements and therefore should activate the area
        # button
        if "area" not in self.track_df.columns:
            if self.feature_widget.feature == "area":
                self.feature_widget._toggle_feature_mode()
            self.feature_widget.show_area_radio.setEnabled(False)
        else:
            self.feature_widget.show_area_radio.setEnabled(True)

        # if reset_view, we got new data and want to reset display and feature before calling the plot update
        if reset_view:
            self.lineage_df = pd.DataFrame()
            self.mode = "all"
            self.mode_widget.show_all_radio.setChecked(True)
            self.view_direction = "vertical"
            self.feature = "tree"
            self.feature_widget.show_tree_radio.setChecked(True)

        # also update the navigation widget
        self.navigation_widget.track_df = self.track_df
        self.navigation_widget.lineage_df = self.lineage_df

        # check which view to set
        if self.mode == "lineage":
            self._update_lineage_df()
            self.tree_widget.update(
                self.lineage_df,
                self.view_direction,
                self.feature,
                self.selected_nodes,
                reset_view=reset_view,
            )

        else:
            self.tree_widget.update(
                self.track_df,
                self.view_direction,
                self.feature,
                self.selected_nodes,
                reset_view=reset_view,
            )

    def _set_mode(self, mode: str) -> None:
        """Set the display mode to all or lineage view. Currently, linage
        view is always horizontal and all view is always vertical.

        Args:
            mode (str): The mode to set the view to. Options are "all" or "lineage"
        """
        if mode not in ["all", "lineage"]:
            raise ValueError(f"Mode must be 'all' or 'lineage', got {mode}")

        self.mode = mode
        if mode == "all":
            if self.feature == "tree":
                self.view_direction = "vertical"
            else:
                self.view_direction = "horizontal"
            df = self.track_df
        elif mode == "lineage":
            self.view_direction = "horizontal"
            self._update_lineage_df()
            df = self.lineage_df
        self.navigation_widget.view_direction = self.view_direction
        self.tree_widget.update(
            df, self.view_direction, self.feature, self.selected_nodes
        )

    def _set_feature(self, feature: str) -> None:
        """Set the feature mode to 'tree' or 'area'. For this the view is always
        horizontal.

        Args:
            feature (str): The feature to plot. Options are "tree" or "area"
        """
        if feature not in ["tree", "area"]:
            raise ValueError(f"Feature must be 'tree' or 'area', got {feature}")

        self.feature = feature
        if feature == "tree" and self.mode == "all":
            self.view_direction = "vertical"
        else:
            self.view_direction = "horizontal"
        self.navigation_widget.view_direction = self.view_direction

        if self.mode == "all":
            df = self.track_df
        if self.mode == "lineage":
            df = self.lineage_df

        self.navigation_widget.feature = self.feature
        self.tree_widget.update(
            df, self.view_direction, self.feature, self.selected_nodes
        )

    def _update_lineage_df(self) -> None:
        """Subset dataframe to include only nodes belonging to the current lineage"""

        if len(self.selected_nodes) == 0 and not self.lineage_df.empty:
            # try to restore lineage df based on previous selection, even if those nodes are now deleted.
            # this is to prevent that deleting nodes will remove those lineages from the lineage view, which is confusing.
            prev_visible_set = set(self.lineage_df["node_id"])
            prev_visible = [
                node for node in prev_visible_set if self.graph.has_node(node)
            ]
            visible = []
            for node_id in prev_visible:
                visible += extract_lineage_tree(self.graph, node_id)
                if set(prev_visible).issubset(visible):
                    break
        else:
            visible = []
            for node_id in self.selected_nodes:
                visible += extract_lineage_tree(self.graph, node_id)
        self.lineage_df = self.track_df[
            self.track_df["node_id"].isin(visible)
        ].reset_index()
        self.lineage_df["x_axis_pos"] = (
            self.lineage_df["x_axis_pos"].rank(method="dense").astype(int) - 1
        )
        self.navigation_widget.lineage_df = self.lineage_df
