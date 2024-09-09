import pandas as pd
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from motile_plugin.utils.node_selection import NodeSelectionList


class NavigationWidget(QWidget):
    def __init__(
        self,
        track_df: pd.DataFrame,
        view_direction: str,
        selected_nodes: NodeSelectionList,
    ):
        """Widget for controlling navigation in the tree widget

        Args:
            track_df (pd.DataFrame): The dataframe holding the track information
            view_direction (str): The view direction of the tree widget. Options: "vertical", "horizontal".
            selected_nodes (NodeSelectionList): The list of selected nodes.
        """

        super().__init__()
        self.track_df = track_df
        self.view_direction = view_direction
        self.selected_nodes = selected_nodes

        navigation_box = QGroupBox("Navigation [\u2b05 \u27a1 \u2b06 \u2b07]")
        navigation_layout = QHBoxLayout()
        left_button = QPushButton("\u2b05")
        right_button = QPushButton("\u27a1")
        up_button = QPushButton("\u2b06")
        down_button = QPushButton("\u2b07")

        left_button.clicked.connect(lambda: self.move("left"))
        right_button.clicked.connect(lambda: self.move("right"))
        up_button.clicked.connect(lambda: self.move("up"))
        down_button.clicked.connect(lambda: self.move("down"))

        navigation_layout.addWidget(left_button)
        navigation_layout.addWidget(right_button)
        navigation_layout.addWidget(up_button)
        navigation_layout.addWidget(down_button)
        navigation_box.setLayout(navigation_layout)
        navigation_box.setMaximumWidth(250)

        layout = QHBoxLayout()
        layout.addWidget(navigation_box)

        self.setLayout(layout)

    def move(self, direction: str) -> None:
        """Move in the given direction on the tree view. Will select the next
        node in that direction, based on the orientation of the widget.

        Args:
            direction (str): The direction to move. Options: "up", "down",
                "left", "right"
        """

        if direction == "left":
            if self.view_direction == "horizontal":
                self.select_predecessor()
            else:
                self.select_next_track(forward=False)
        elif direction == "right":
            if self.view_direction == "horizontal":
                self.select_successor()
            else:
                self.select_next_track()
        elif direction == "up":
            if self.view_direction == "horizontal":
                self.select_next_track()
            else:
                self.select_predecessor()
        elif direction == "down":
            if self.view_direction == "horizontal":
                self.select_next_track(forward=False)
            else:
                self.select_successor()
        else:
            raise ValueError(
                f"Direction must be one of 'left', 'right', 'up', 'down', got {direction}"
            )

    def select_next_track(self, forward=True) -> None:
        """Select the node at the same time point in an adjacent track.

        Args:
            forward (bool, optional): If true, pick the next track (right/down).
                Otherwise, pick the previous track (left/up). Defaults to True.
        """
        if len(self.selected_nodes) > 0:
            node_id = self.selected_nodes[0]
            x_axis_pos = self.track_df.loc[
                self.track_df["node_id"] == node_id, "x_axis_pos"
            ].values[0]
            t = self.track_df.loc[
                self.track_df["node_id"] == node_id, "t"
            ].values[0]
            if forward:
                neighbors = self.track_df.loc[
                    (self.track_df["x_axis_pos"] > x_axis_pos)
                    & (self.track_df["t"] == t)
                ]
            else:
                neighbors = self.track_df.loc[
                    (self.track_df["x_axis_pos"] < x_axis_pos)
                    & (self.track_df["t"] == t)
                ]
            if not neighbors.empty:
                # Find the closest index label
                closest_index_label = (
                    (neighbors["x_axis_pos"] - x_axis_pos).abs().idxmin()
                )
                neighbor = neighbors.loc[closest_index_label, "node_id"]
                self.selected_nodes.add(neighbor)

    def select_predecessor(self) -> None:
        """Jump one node up"""

        if len(self.selected_nodes) > 0:
            node_id = self.selected_nodes[0]
            parent_id = self.track_df.loc[
                self.track_df["node_id"] == node_id, "parent_id"
            ].values[0]
            parent_row = self.track_df.loc[
                self.track_df["node_id"] == parent_id
            ]
            if not parent_row.empty:
                self.selected_nodes.add(parent_row["node_id"].values[0])

    def select_successor(self) -> None:
        """Jump one node down"""

        if len(self.selected_nodes) > 0:
            node_id = self.selected_nodes[0]
            children = self.track_df.loc[self.track_df["parent_id"] == node_id]
            if not children.empty:
                child = children.to_dict("records")[0]
                self.selected_nodes.add(child["node_id"])
