from typing import List

import napari
import numpy as np
import pandas as pd
import pyqtgraph as pg
from psygnal import Signal
from PyQt5.QtGui import QColor, QMouseEvent
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from motile_plugin.backend.motile_run import MotileRun
from motile_plugin.widgets.tracking_view_controller import (
    TrackingViewController,
)

from ..utils.tree_widget_utils import extract_lineage_tree


class TreeWidget(QWidget):
    """pyqtgraph-based widget for lineage tree visualization and interactive annotation of nodes and edges"""

    node_selected = Signal(
        str, bool
    )  # boolean indicates if append to existing selection or not

    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.track_df = pd.DataFrame()
        self.pseudo_df = pd.DataFrame()
        self.selection = []
        self.graph = None
        self.mode = "all"

        view_controller = TrackingViewController.get_instance(viewer)
        self.colormap = view_controller.colormap
        self.node_selected.connect(view_controller.select_node)
        view_controller.tracking_layers_updated.connect(self.update_track_data)
        view_controller.selection_updated.connect(self._show_selected)

        # Construct the tree view pyqtgraph widget
        layout = QVBoxLayout()
        self.tree_widget = pg.PlotWidget()
        self.tree_widget.setTitle("Lineage Tree")
        self.tree_widget.setLabel("left", text="Time Point")
        self.tree_widget.getAxis("bottom").setStyle(showValues=False)
        self.tree_widget.invertY(True)  # to show tracks from top to bottom
        self.g = pg.GraphItem()
        self.g.scatter.sigClicked.connect(self._on_click)
        self.tree_widget.addItem(self.g)

        # Add radiobuttons for switching between different display modes
        display_box = QGroupBox("Display")
        display_layout = QHBoxLayout()
        button_group = QButtonGroup()
        self.show_all_radio = QRadioButton("All cells")
        self.show_all_radio.setChecked(True)  # Set the default option
        self.show_all_radio.clicked.connect(lambda: self._set_mode("all"))
        self.show_lineage_radio = QRadioButton("Current lineage")
        self.show_lineage_radio.clicked.connect(
            lambda: self._set_mode("lineage")
        )
        button_group.addButton(self.show_all_radio)
        button_group.addButton(self.show_lineage_radio)
        display_layout.addWidget(self.show_all_radio)
        display_layout.addWidget(self.show_lineage_radio)
        display_box.setLayout(display_layout)
        display_box.setMaximumWidth(250)

        layout.addWidget(display_box)

        layout.addWidget(self.tree_widget)

        self.setLayout(layout)

    def _set_mode(self, mode: str):
        """Change the display mode"""

        self.mode = mode
        if not self.pseudo_df.empty:
            if mode == "lineage":
                self._update(pins=[], subset=True)
            else:
                self._update(pins=[], subset=False)

    def update_track_data(self, motile_run: MotileRun):
        """Fetch the track_df directly from the new motile_run"""

        self.track_df = motile_run.track_df
        self.graph = motile_run.tracks
        self._update(pins=[], subset=False)

    def _on_click(self, _, points: np.ndarray, ev: QMouseEvent) -> None:
        """Adds the selected point to the selected_nodes list"""

        modifiers = ev.modifiers()
        clicked_point = points[0]
        index = clicked_point.index()  # Get the index of the clicked point

        # find the corresponding element in the list of dicts
        node_df = self.pseudo_df[self.pseudo_df["pseudo_index"] == index]
        if not node_df.empty:
            node_df.iloc[
                0
            ].to_dict()  # Convert the filtered result to a dictionary
        append = Qt.ShiftModifier == modifiers
        self.node_selected.emit(node_df.iloc[0].to_dict(), append)

    def _show_selected(self, selection):
        """Update the graph, increasing the size of selected node(s)"""

        self.selection = selection

        if self.mode == "lineage":
            self._update(pins=[], subset=True)

        size = (
            self.size.copy()
        )  # just copy the size here to keep the original self.size intact

        outlines = self.outline_pen.copy()

        for i, node in enumerate(selection):
            pseudo_index = self.pseudo_df.loc[
                self.pseudo_df["index"] == node["index"], "pseudo_index"
            ]
            if not pseudo_index.empty:
                pseudo_index = pseudo_index.values[0]
                size[pseudo_index] = size[pseudo_index] + 5
                outlines[pseudo_index] = pg.mkPen(color="c", width=2)
                if i == 0:
                    self._center_view(node["x_axis_pos"], node["t"])

        self.tree_widget.plotItem.items[0].scatter.opts["pen"] = outlines

        self.g.setData(
            pos=self.pos,
            adj=self.adj,
            symbolBrush=self.symbolBrush,
            size=size,
            symbol=self.symbols,
            pen=self.pen,
        )

    def _update(self, pins: List, subset: bool = False) -> None:
        """Redraw the pyqtgraph object with the given tracks dataframe"""

        pos = []
        pos_colors = []
        adj = []
        adj_colors = []
        symbols = []
        sizes = []
        if self.track_df is None:
            self.g.scatter.clear()
            return

        self.g.scatter.clear()
        if subset:
            if len(self.selection) == 0:
                self.g.scatter.clear()
                return
            else:
                visible = extract_lineage_tree(
                    self.graph, self.selection[0]["node_id"]
                )
            self.pseudo_df = self.track_df[
                self.track_df["node_id"].isin(visible)
            ]
            self.pseudo_df = self.pseudo_df.reset_index()
        else:
            self.pseudo_df = self.track_df

        self.pseudo_df["pseudo_index"] = self.pseudo_df.index

        for _, node in self.pseudo_df.iterrows():
            if node["symbol"] == "triangle_up":
                symbols.append("t1")
            elif node["symbol"] == "x":
                symbols.append("x")
            else:
                symbols.append("o")

            if node["annotated"]:
                pos_colors.append([255, 0, 0, 255])  # edits displayed in red
                sizes.append(13)
            else:
                pos_colors.append(node["color"])
                sizes.append(8)

            if subset:
                pos.append([node["t"], node["x_axis_pos"]])
            else:
                pos.append([node["x_axis_pos"], node["t"]])
            parent = node["parent_id"]
            if parent != 0:
                parent_df = self.pseudo_df[self.pseudo_df["node_id"] == parent]
                if not parent_df.empty:
                    parent_dict = parent_df.iloc[0]
                    adj.append(
                        [parent_dict["pseudo_index"], node["pseudo_index"]]
                    )
                    if (parent_dict["node_id"], node["node_id"]) in pins:
                        adj_colors.append(
                            [255, 0, 0, 255, 255, 1]
                        )  # pinned edges displayed in red
                    else:
                        adj_colors.append(
                            parent_dict["color"].tolist() + [255, 1]
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

        self.tree_widget.plotItem.items[0].scatter.opts["pen"] = pg.mkPen(
            QColor(150, 150, 150)
        )  # first reset the pen to avoid problems with length mismatch between the different properties

        if len(self.pos) > 0:
            self.g.setData(
                pos=self.pos,
                adj=self.adj,
                symbol=self.symbols,
                symbolBrush=self.symbolBrush,
                size=self.size,
                pen=self.pen,
            )
            self.tree_widget.plotItem.items[0].scatter.opts[
                "pen"
            ] = self.outline_pen
        else:
            self.g.scatter.clear()

        if self.mode == "lineage":
            self.tree_widget.setLabel("bottom", text="Time Point")
            self.tree_widget.setLabel("left", text="")
            self.tree_widget.getAxis("bottom").setStyle(showValues=True)
            self.tree_widget.getAxis("left").setStyle(showValues=False)
            self.tree_widget.invertY(False)
        else:
            self.tree_widget.setLabel("left", text="Time Point")
            self.tree_widget.setLabel("bottom", text="")
            self.tree_widget.getAxis("bottom").setStyle(showValues=False)
            self.tree_widget.getAxis("left").setStyle(showValues=True)
            self.tree_widget.invertY(True)  # to show tracks from top to bottom

    def _center_view(self, center_x: int, center_y: int):
        """Center the Viewbox on given coordinates"""

        if self.mode == "lineage":
            center_x, center_y = (
                center_y,
                center_x,
            )  # flip because the axes have changed in lineage mode

        view_box = self.tree_widget.plotItem.getViewBox()
        current_range = (
            view_box.viewRange()
        )  # Get the current range of the viewbox

        x_range = current_range[0]
        y_range = current_range[1]

        # Check if the new center is within the current range
        if (
            x_range[0] <= center_x <= x_range[1]
            and y_range[0] <= center_y <= y_range[1]
        ):
            return  # The point is already within the current range, no need to move the view

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

        # Set the new range to the viewbox
        view_box.setRange(xRange=new_x_range, yRange=new_y_range, padding=0)
