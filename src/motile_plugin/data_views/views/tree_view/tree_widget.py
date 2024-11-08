# do not put the from __future__ import annotations as it breaks the injection

import napari
import numpy as np
import pandas as pd
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible

from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer

from .navigation_widget import NavigationWidget
from .tree_plot import TreePlot
from .tree_view_feature_widget import TreeViewFeatureWidget
from .tree_view_mode_widget import TreeViewModeWidget
from .tree_widget_utils import (
    extract_lineage_tree,
    extract_sorted_tracks,
)


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
