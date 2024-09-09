import napari
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtGui import QColor, QMouseEvent
from pyqtgraph.Qt import QtCore
from qtpy.QtCore import Qt
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


class TreeWidget(QWidget):
    """pyqtgraph-based widget for lineage tree visualization and navigation"""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.track_df = pd.DataFrame()
        self.lineage_df = pd.DataFrame()
        self.graph = None
        self.mode = "all"
        self.pins = []

        # initialize empty graph data objects
        self._reset_plotting_data()

        self.tracks_viewer = TracksViewer.get_instance(viewer)
        self.colormap = self.tracks_viewer.colormap
        self.selected_nodes = self.tracks_viewer.selected_nodes
        self.selected_nodes.list_updated.connect(self._show_selected)
        self.tracks_viewer.tracks_updated.connect(self._update_track_data)

        # Construct the tree view pyqtgraph widget
        layout = QVBoxLayout()

        self.tree_widget: pg.PlotWidget = self._get_tree_widget()
        self.g = pg.GraphItem()
        self.g.scatter.sigClicked.connect(self._on_click)
        self.tree_widget.addItem(self.g)

        # Add radiobuttons for switching between different display modes
        self.mode_widget = TreeViewModeWidget()
        self.mode_widget.change_mode.connect(self._set_mode)

        # Add navigation widget
        self.navigation_widget = NavigationWidget(
            self.track_df, self.mode, self.selected_nodes
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

        # check if the tracks_viewer already holds any tracks, if so, immediately call the update_tracks function
        if self.tracks_viewer.tracks is not None:
            self._update_track_data()

    def _get_tree_widget(self) -> pg.PlotWidget:
        """Construct the pyqtgraph treewidget"""

        vb = CustomViewBox()
        tree_widget = pg.PlotWidget(viewBox=vb)
        tree_widget.setFocusPolicy(Qt.StrongFocus)
        tree_widget.setTitle("Lineage Tree")
        tree_widget.setLabel("left", text="Time Point")
        tree_widget.getAxis("bottom").setStyle(showValues=False)
        tree_widget.invertY(True)  # to show tracks from top to bottom

        return tree_widget

    def keyPressEvent(self, event) -> None:
        """Catch arrow key presses to navigate in the tree"""
        direction_map = {
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
        }

        if event.key() == Qt.Key_L:
            self.mode_widget._toggle_display_mode()
        else:
            if event.key() not in direction_map:
                return
            self.navigation_widget.select_next_node(direction_map[event.key()])

    def _reset_plotting_data(self) -> None:
        """Reset the plotting data if it had been generated before"""

        self.pos = None
        self.adj = None
        self.symbolBrush = None
        self.symbols = None
        self.pen = None
        self.outline_pen = None
        self.node_ids = None

        self.lineage_pos = None
        self.lineage_adj = None
        self.lineage_symbolBrush = None
        self.lineage_symbols = None
        self.lineage_pen = None
        self.lineage_outline_pen = None
        self.lineage_node_ids = None

    def _update_track_data(self) -> None:

        self.track_df = extract_sorted_tracks(
            self.tracks_viewer.tracks, self.tracks_viewer.colormap
        )
        self.navigation_widget.track_df = (
            self.track_df
        )  # also update the navagiation widget
        tracks = self.tracks_viewer.tracks
        if tracks is None or tracks.graph is None:
            self.graph = None
        else:
            self.graph = self.tracks_viewer.tracks.graph

        # set mode back to all
        self.mode = "all"
        self._reset_plotting_data()
        self._update()

    def _set_mode(self, mode: str) -> None:
        """Change the display mode"""

        self.mode = mode
        self.navigation_widget.mode = mode
        self._update()
        self.tree_widget.autoRange()

    def _on_click(self, _, points: np.ndarray, ev: QMouseEvent) -> None:
        """Adds the selected point to the selected_nodes list"""

        modifiers = ev.modifiers()
        node_id = points[0].data()
        append = Qt.ShiftModifier == modifiers
        self.selected_nodes.add(node_id, append)

    def _show_selected(self) -> None:
        """Update the graph, increasing the size of selected node(s)"""

        # reset to default size and color to avoid problems with the array lengths
        self.g.scatter.setPen(pg.mkPen(QColor(150, 150, 150)))
        self.g.scatter.setSize(10)

        update_view = False
        if self.mode == "lineage":

            # check whether we have switched to a new lineage that needs to be computed or if we are still on the same lineage and can skip this step
            if not all(
                node in self.selected_nodes
                for node in np.unique(self.lineage_df["node_id"].values)
            ):
                self._create_lineage_df()
                self._create_lineage_pyqtgraph_content()
                update_view = (
                    True  # only update the view when a new lineage is selected
                )
            size = (
                self.lineage_size.copy()
            )  # just copy the size here to keep the original self.lineage_size intact

            outlines = self.lineage_outline_pen.copy()

            for i, node_id in enumerate(self.selected_nodes):
                node_df = self.lineage_df.loc[
                    self.lineage_df["node_id"] == node_id
                ]
                if not node_df.empty:
                    x_axis_pos = node_df["x_axis_pos"].values[0]
                    t = node_df["t"].values[0]

                    # Update size and outline
                    index = self.lineage_node_ids.index(node_id)
                    size[index] += 5
                    outlines[index] = pg.mkPen(color="c", width=2)

                    # Center view based on the first selected node
                    if i == 0:
                        self._center_view(x_axis_pos, t)

            if update_view:
                self.g.setData(
                    pos=self.lineage_pos,
                    adj=self.lineage_adj,
                    symbol=self.lineage_symbols,
                    symbolBrush=self.lineage_symbolBrush,
                    pen=self.lineage_pen,
                    data=self.lineage_node_ids,
                )
                self.tree_widget.autoRange()

            self.g.scatter.setPen(outlines)
            self.g.scatter.setSize(size)

        else:
            size = (
                self.size.copy()
            )  # just copy the size here to keep the original self.size intact

            outlines = self.outline_pen.copy()
            for i, node_id in enumerate(self.selected_nodes):
                node_df = self.track_df.loc[
                    self.track_df["node_id"] == node_id
                ]
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

    def _create_lineage_df(self) -> None:
        """Subset dataframe to include only nodes belonging to the current lineage"""

        visible = []
        for node_id in self.selected_nodes:
            visible += extract_lineage_tree(self.graph, node_id)
        self.lineage_df = self.track_df[
            self.track_df["node_id"].isin(visible)
        ].reset_index()

    def _create_lineage_pyqtgraph_content(self) -> None:
        """Create graph data for a specific lineage"""

        pos = []
        pos_colors = []
        adj = []
        adj_colors = []
        symbols = []
        sizes = []
        self.lineage_node_ids = []

        if not self.lineage_df.empty:
            for i, node in self.lineage_df.iterrows():
                if node["symbol"] == "triangle_up":
                    symbols.append("t1")
                elif node["symbol"] == "x":
                    symbols.append("x")
                else:
                    symbols.append("o")
                pos_colors.append(node["color"])
                self.lineage_node_ids.append(node["node_id"])
                sizes.append(8)

                pos.append([node["t"], node["x_axis_pos"]])

                parent = node["parent_id"]
                if parent != 0:
                    parent_df = self.lineage_df[
                        self.lineage_df["node_id"] == parent
                    ]
                    if not parent_df.empty:

                        adj.append([parent_df.index[0], i])
                        if (
                            parent_df["node_id"].values[0],
                            node["node_id"],
                        ) in self.pins:
                            adj_colors.append(
                                [255, 0, 0, 255, 255, 1]
                            )  # pinned edges displayed in red
                        else:
                            adj_colors.append(
                                parent_df["color"].values[0].tolist()
                                + [255, 1]
                            )

        self.lineage_pos = np.array(pos)
        self.lineage_adj = np.array(adj)
        self.lineage_symbols = symbols
        self.lineage_symbolBrush = np.array(pos_colors)
        self.lineage_pen = np.array(adj_colors)
        self.lineage_size = np.array(sizes)

        self.lineage_outline_pen = np.array(
            [
                pg.mkPen(QColor(150, 150, 150))
                for i in range(len(self.lineage_pos))
            ]
        )

    def _create_pyqtgraph_content(self) -> None:
        """Calculate the pyqtgraph data for plotting"""

        pos = []
        pos_colors = []
        adj = []
        adj_colors = []
        symbols = []
        sizes = []
        self.node_ids = []

        if self.track_df is not None:
            for i, node in self.track_df.iterrows():
                if node["symbol"] == "triangle_up":
                    symbols.append("t1")
                elif node["symbol"] == "x":
                    symbols.append("x")
                else:
                    symbols.append("o")

                pos_colors.append(node["color"])
                sizes.append(8)

                pos.append([node["x_axis_pos"], node["t"]])
                self.node_ids.append(node["node_id"])
                parent = node["parent_id"]
                if parent != 0:
                    parent_df = self.track_df[
                        self.track_df["node_id"] == parent
                    ]
                    if not parent_df.empty:
                        adj.append([parent_df.index[0], i])

                        if (
                            parent_df["node_id"].values[0],
                            node["node_id"],
                        ) in self.pins:
                            adj_colors.append(
                                [255, 0, 0, 255, 255, 1]
                            )  # pinned edges displayed in red
                        else:
                            adj_colors.append(
                                parent_df["color"].values[0].tolist()
                                + [255, 1]
                            )

        self.pos = np.array(pos)
        self.adj = np.array(adj)
        self.symbols = symbols
        self.symbolBrush = np.array(pos_colors)
        self.pen = np.array(adj_colors)
        self.size = np.array(sizes)

        self.outline_pen = np.array(
            [pg.mkPen(QColor(150, 150, 150)) for i in range(len(self.pos))]
        )

    def _update(self) -> None:
        """Redraw the pyqtgraph object with the given tracks dataframe"""

        self.g.scatter.setPen(
            pg.mkPen(QColor(150, 150, 150))
        )  # first reset the pen to avoid problems with length mismatch between the different properties
        self.g.scatter.setSize(10)
        self.g.scatter.clear()

        if self.mode == "lineage":
            self._create_lineage_df()
            self._create_lineage_pyqtgraph_content()
            if len(self.lineage_pos) > 0:
                self.g.setData(
                    pos=self.lineage_pos,
                    adj=self.lineage_adj,
                    symbol=self.lineage_symbols,
                    symbolBrush=self.lineage_symbolBrush,
                    pen=self.lineage_pen,
                    data=self.lineage_node_ids,
                )
                self.g.scatter.setPen(self.lineage_outline_pen)
                self.g.scatter.setSize(self.lineage_size)

            self.tree_widget.setLabel("bottom", text="Time Point")
            self.tree_widget.setLabel("left", text="")
            self.tree_widget.getAxis("bottom").setStyle(showValues=True)
            self.tree_widget.getAxis("left").setStyle(showValues=False)
            self.tree_widget.invertY(False)

        if self.mode == "all":
            if self.pos is None:
                self._create_pyqtgraph_content()
            if len(self.pos) > 0:
                self.g.setData(
                    pos=self.pos,
                    adj=self.adj,
                    symbol=self.symbols,
                    symbolBrush=self.symbolBrush,
                    pen=self.pen,
                    data=self.node_ids,
                )
                self.g.scatter.setPen(self.outline_pen)
                self.g.scatter.setSize(self.size)
            else:
                self.g.scatter.clear()

            self.tree_widget.setLabel("left", text="Time Point")
            self.tree_widget.setLabel("bottom", text="")
            self.tree_widget.getAxis("bottom").setStyle(showValues=False)
            self.tree_widget.getAxis("left").setStyle(showValues=True)
            self.tree_widget.invertY(True)  # to show tracks from top to bottom

        self.tree_widget.autoRange()

    def _center_view(self, center_x: int, center_y: int):
        """Center the Viewbox on given coordinates"""

        if self.mode == "lineage":
            center_x, center_y = (
                center_y,
                center_x,
            )  # flip because the axes have changed in lineage mode

        view_box = self.tree_widget.plotItem.getViewBox()
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
