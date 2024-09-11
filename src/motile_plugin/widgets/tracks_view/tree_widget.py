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

from motile_plugin.utils.tree_widget_utils import (
    extract_lineage_tree,
    extract_sorted_tracks,
)
from motile_plugin.widgets.tracks_view.tracks_viewer import (
    TracksViewer,
)

from .navigation_widget import NavigationWidget
from .tree_view_mode_widget import TreeViewModeWidget


class CustomViewBox(pg.ViewBox):
    def __init__(self, *args, **kwds):
        kwds["enableMenu"] = False
        pg.ViewBox.__init__(self, *args, **kwds)
        # self.setMouseMode(self.RectMode)

    ## reimplement right-click to zoom out
    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.RightButton:
            self.autoRange()

    ## reimplement mouseDragEvent to disable continuous axis zoom
    def mouseDragEvent(self, ev, axis=None):
        if ev.modifiers() == Qt.ShiftModifier:
            # If Shift is pressed, enable rectangular zoom mode
            self.setMouseMode(self.RectMode)
        else:
            # Otherwise, disable rectangular zoom mode
            self.setMouseMode(self.PanMode)

        if (
            axis is not None
            and ev.button() == QtCore.Qt.MouseButton.RightButton
        ):
            ev.ignore()
        else:
            pg.ViewBox.mouseDragEvent(self, ev, axis=axis)


class TreePlot(pg.PlotWidget):
    node_clicked = Signal(Any, bool)  # node_id, append

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
        self.g = pg.GraphItem()
        self.g.scatter.sigClicked.connect(self._on_click)
        self.addItem(self.g)
        self.set_view("vertical")

    def update(
        self,
        track_df: pd.DataFrame,
        view_direction: str,
        selected_nodes: list[Any],
    ):
        """Update the entire view, including the data, view direction, and
        selected nodes

        Args:
            track_df (pd.DataFrame): The dataframe containing the graph data
            view_direction (str): The view direction
            selected_nodes (list[Any]): The currently selected nodes to be highlighted
        """
        self.set_data(track_df)
        self.set_view(view_direction)
        self._update_viewed_data()  # this can be expensive
        self.set_selection(selected_nodes)

    def set_view(self, view_direction: str):
        """Set the view direction, saving the new value as an attribute and
        changing the axes labels. Shortcuts if the view direction is already
        correct. Does not actually update the rendered graph (need to call
        _update_viewed_data).

        Args:
            view_direction (str): "horizontal" or "vertical"
        """
        if view_direction == self.view_direction:
            return
        self.view_direction = view_direction
        if view_direction == "vertical":
            self.setLabel("left", text="Time Point")
            self.getAxis("left").setStyle(showValues=True)
            self.getAxis("bottom").setStyle(showValues=False)
            self.invertY(True)  # to show tracks from top to bottom
        elif view_direction == "horizontal":
            self.setLabel("bottom", text="Time Point")
            self.getAxis("bottom").setStyle(showValues=True)
            self.setLabel("left", text="")
            self.getAxis("left").setStyle(showValues=False)
            self.invertY(False)

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

    def set_data(self, track_df: pd.DataFrame) -> None:
        """Updates the stored pyqtgraph content based on the given dataframe.
        Does not render the new information (need to call _update_viewed_data).

        Args:
            track_df (pd.DataFrame): The tracks df to compute the pyqtgraph
                content for. Can be all lineages or any subset of them.
        """
        self.track_df = track_df
        self._create_pyqtgraph_content(track_df)

    def _update_viewed_data(self):
        self.g.scatter.setPen(
            pg.mkPen(QColor(150, 150, 150))
        )  # first reset the pen to avoid problems with length mismatch between the different properties
        self.g.scatter.setSize(10)
        if len(self._pos) == 0 or self.view_direction == "vertical":
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
        self.autoRange()

    def _create_pyqtgraph_content(self, track_df: pd.DataFrame) -> None:
        """Parse the given track_df into the format that pyqtgraph expects
        and save the information as attributes.

        Args:
            track_df (pd.DataFrame): The dataframe containing the graph to be
                rendered in the tree view. Can be all lineages or a subset.
        """
        self._pos = []
        self.adj = []
        self.symbols = []
        self.symbolBrush = []
        self.pen = []
        self.sizes = []

        if track_df is not None and not track_df.empty:
            self.symbols = track_df["symbol"].to_list()
            self.symbolBrush = track_df["color"].to_numpy()
            self._pos = track_df[["x_axis_pos", "t"]].to_numpy()
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

    def set_selection(self, selected_nodes: list[Any]) -> None:
        """Set the provided list of nodes to be selected. Increases the size
        and highlights the outline with blue. Also centers the view
        if the first selected node is not visible in the current canvas.

        Args:
            selected_nodes (list[Any]): A list of node ids to be selected.
        """

        # reset to default size and color to avoid problems with the array lengths
        self.g.scatter.setPen(pg.mkPen(QColor(150, 150, 150)))
        self.g.scatter.setSize(10)

        size = (
            self.sizes.copy()
        )  # just copy the size here to keep the original self.sizes intact

        outlines = self.outline_pen.copy()
        for i, node_id in enumerate(selected_nodes):
            node_df = self.track_df.loc[self.track_df["node_id"] == node_id]
            if not node_df.empty:
                x_axis_pos = node_df["x_axis_pos"].values[0]
                t = node_df["t"].values[0]

                # Update size and outline
                index = self.node_ids.index(node_id)
                size[index] += 5
                outlines[index] = pg.mkPen(color="c", width=2)

                # Center view based on the first selected node
                if i == 0:
                    self._center_view(x_axis_pos, t)

        self.g.scatter.setPen(outlines)
        self.g.scatter.setSize(size)

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
        self.lineage_df = (
            pd.DataFrame()
        )  # the currently viewed subset of lineages
        self.graph = None
        self.mode = "all"  # options: "all", "lineage"
        self.view_direction = "vertical"  # options: "horizontal", "vertical"

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.selected_nodes = self.tracks_viewer.selected_nodes
        self.selected_nodes.list_updated.connect(self._update_selected)
        self.tracks_viewer.tracks_updated.connect(self._update_track_data)

        # Construct the tree view pyqtgraph widget
        layout = QVBoxLayout()

        self.tree_widget: TreePlot = TreePlot()
        self.tree_widget.node_clicked.connect(self.selected_nodes.add)

        # Add radiobuttons for switching between different display modes
        self.mode_widget = TreeViewModeWidget()
        self.mode_widget.change_mode.connect(self._set_mode)

        # Add navigation widget
        self.navigation_widget = NavigationWidget(
            self.track_df,
            self.lineage_df,
            self.view_direction,
            self.selected_nodes,
        )

        # Construct a toolbar and set main layout
        panel_layout = QHBoxLayout()
        panel_layout.addWidget(self.mode_widget)
        panel_layout.addWidget(self.navigation_widget)

        panel = QWidget()
        panel.setLayout(panel_layout)
        panel.setMaximumWidth(520)

        layout.addWidget(panel)
        layout.addWidget(self.tree_widget)

        self.setLayout(layout)
        self._update_track_data()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Catch arrow key presses to navigate in the tree

        Args:
            event (QKeyEvent): The Qt Key event
        """
        direction_map = {
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
        }

        if event.key() == Qt.Key_L:
            self.mode_widget._toggle_display_mode()
        elif event.key() == Qt.Key_X:  # only allow mouse zoom scrolling in X
            self.tree_widget.setMouseEnabled(x=True, y=False)
        elif event.key() == Qt.Key_Y:  # only allow mouse zoom scrolling in Y
            self.tree_widget.setMouseEnabled(x=False, y=True)
        else:
            if event.key() not in direction_map:
                return
            self.navigation_widget.move(direction_map[event.key()])

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
                self.lineage_df, self.view_direction, self.selected_nodes
            )
        else:
            self.tree_widget.set_selection(self.selected_nodes)

    def _update_track_data(self) -> None:
        """Called when the TracksViewer emits the tracks_updated signal, indicating
        that a new set of tracks should be viewed.
        """
        if self.tracks_viewer.tracks is None:
            self.track_df = pd.DataFrame()
            self.graph = None
        else:
            self.track_df = extract_sorted_tracks(
                self.tracks_viewer.tracks, self.tracks_viewer.colormap
            )
            self.graph = self.tracks_viewer.tracks.graph

        self.lineage_df = pd.DataFrame()
        # also update the navigation widget
        self.navigation_widget.track_df = self.track_df
        self.navigation_widget.lineage_df = self.lineage_df

        # set mode back to all and view to vertical
        self._set_mode("all")
        self.tree_widget.update(
            self.track_df, self.view_direction, self.selected_nodes
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
            self.view_direction = "vertical"
            df = self.track_df
        elif mode == "lineage":
            if len(self.selected_nodes) == 0:
                # don't change the mode
                pass
            self.view_direction = "horizontal"
            self._update_lineage_df()
            df = self.lineage_df
        self.navigation_widget.view_direction = self.view_direction
        self.tree_widget.update(df, self.view_direction, self.selected_nodes)

    def _update_lineage_df(self) -> None:
        """Subset dataframe to include only nodes belonging to the current lineage"""
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
