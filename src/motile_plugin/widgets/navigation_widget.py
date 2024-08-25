import pandas as pd
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from ..utils.node_selection import NodeSelectionList


class NavigationWidget(QWidget):
    """Widget for controlling navigation in the tree widget"""

    def __init__(
        self,
        track_df: pd.DataFrame,
        mode: str,
        selected_nodes: NodeSelectionList,
    ):
        super().__init__()
        self.track_df = track_df
        self.mode = mode
        self.selected_nodes = selected_nodes

        navigation_box = QGroupBox("Navigation [\u2b05 \u27a1 \u2b06 \u2b07]")
        navigation_layout = QHBoxLayout()
        left_button = QPushButton("\u2b05")
        right_button = QPushButton("\u27a1")
        up_button = QPushButton("\u2b06")
        down_button = QPushButton("\u2b07")

        left_button.clicked.connect(lambda: self.select_next_node("left"))
        right_button.clicked.connect(lambda: self.select_next_node("right"))
        up_button.clicked.connect(lambda: self.select_next_node("up"))
        down_button.clicked.connect(lambda: self.select_next_node("down"))

        navigation_layout.addWidget(left_button)
        navigation_layout.addWidget(right_button)
        navigation_layout.addWidget(up_button)
        navigation_layout.addWidget(down_button)
        navigation_box.setLayout(navigation_layout)
        navigation_box.setMaximumWidth(250)

        layout = QHBoxLayout()
        layout.addWidget(navigation_box)

        self.setLayout(layout)

    def select_next_node(self, direction: str) -> None:
        """Interpret in which direction to jump"""

        if direction == "left":
            if self.mode == "lineage":
                self.select_up()  # redirect because axes are flipped
            else:
                self.select_left()
        elif direction == "right":
            if self.mode == "lineage":
                self.select_down()  # redirect because axes are flipped
            else:
                self.select_right()
        elif direction == "up":
            if self.mode == "lineage":
                self.select_right()  # redirect because axes are flipped
            else:
                self.select_up()
        elif direction == "down":
            if self.mode == "lineage":
                self.select_left()  # redirect because axes are flipped
            else:
                self.select_down()

    def select_left(self) -> None:
        """Jump one node to the left"""

        if len(self.selected_nodes) > 0:
            node_id = self.selected_nodes[0]
            x_axis_pos = self.track_df.loc[
                self.track_df["node_id"] == node_id, "x_axis_pos"
            ].values[0]
            t = self.track_df.loc[
                self.track_df["node_id"] == node_id, "t"
            ].values[0]
            left_neighbors = self.track_df.loc[
                (self.track_df["x_axis_pos"] < x_axis_pos)
                & (self.track_df["t"] == t)
            ]
            if not left_neighbors.empty:
                # Find the closest index label
                closest_index_label = (
                    (left_neighbors["x_axis_pos"] - x_axis_pos).abs().idxmin()
                )
                left_neighbor = left_neighbors.loc[
                    closest_index_label, "node_id"
                ]
                self.selected_nodes.add(left_neighbor)

    def select_right(self) -> None:
        """Jump one node to the right"""

        if len(self.selected_nodes) > 0:
            node_id = self.selected_nodes[0]
            x_axis_pos = self.track_df.loc[
                self.track_df["node_id"] == node_id, "x_axis_pos"
            ].values[0]
            t = self.track_df.loc[
                self.track_df["node_id"] == node_id, "t"
            ].values[0]
            right_neighbors = self.track_df.loc[
                (self.track_df["x_axis_pos"] > x_axis_pos)
                & (self.track_df["t"] == t)
            ]

            if not right_neighbors.empty:
                # Find the closest index label
                closest_index_label = (
                    (right_neighbors["x_axis_pos"] - x_axis_pos).abs().idxmin()
                )
                right_neighbor = right_neighbors.loc[
                    closest_index_label, "node_id"
                ]
                self.selected_nodes.add(right_neighbor)

    def select_up(self) -> None:
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

    def select_down(self) -> None:
        """Jump one node down"""

        if len(self.selected_nodes) > 0:
            node_id = self.selected_nodes[0]
            children = self.track_df.loc[self.track_df["parent_id"] == node_id]
            if not children.empty:
                child = children.to_dict("records")[0]
                self.selected_nodes.add(child["node_id"])
