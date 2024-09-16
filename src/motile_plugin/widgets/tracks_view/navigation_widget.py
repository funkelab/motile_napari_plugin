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
        lineage_df: pd.DataFrame,
        view_direction: str,
        selected_nodes: NodeSelectionList,
        feature: str,
    ):
        """Widget for controlling navigation in the tree widget

        Args:
            track_df (pd.DataFrame): The dataframe holding the track information
            view_direction (str): The view direction of the tree widget. Options: "vertical", "horizontal".
            selected_nodes (NodeSelectionList): The list of selected nodes.
            feature (str): The feature currently being displayed
        """

        super().__init__()
        self.track_df = track_df
        self.lineage_df = lineage_df
        self.view_direction = view_direction
        self.selected_nodes = selected_nodes
        self.feature = feature

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
        if len(self.selected_nodes) == 0:
            return
        node_id = self.selected_nodes[0]

        if direction == "left":
            if self.view_direction == "horizontal":
                next_node = self.get_predecessor(node_id)
            else:
                next_node = self.get_next_track_node(
                    self.track_df, node_id, forward=False
                )
        elif direction == "right":
            if self.view_direction == "horizontal":
                next_node = self.get_successor(node_id)
            else:
                next_node = self.get_next_track_node(self.track_df, node_id)
        elif direction == "up":
            if self.view_direction == "horizontal":
                next_node = self.get_next_track_node(self.lineage_df, node_id)
                if next_node is None:
                    next_node = self.get_next_track_node(
                        self.track_df, node_id
                    )
            else:
                next_node = self.get_predecessor(node_id)
        elif direction == "down":
            if self.view_direction == "horizontal":
                # try navigation within the current lineage_df first
                next_node = self.get_next_track_node(
                    self.lineage_df, node_id, forward=False
                )
                # if not found, look in the whole dataframe
                # to enable jumping to the next node outside the current tree view content
                if next_node is None:
                    next_node = self.get_next_track_node(
                        self.track_df, node_id, forward=False
                    )
            else:
                next_node = self.get_successor(node_id)
        else:
            raise ValueError(
                f"Direction must be one of 'left', 'right', 'up', 'down', got {direction}"
            )
        if next_node is not None:
            self.selected_nodes.add(next_node)

    def get_next_track_node(
        self, df: pd.DataFrame, node_id: str, forward=True
    ) -> str | None:
        """Get the node at the same time point in an adjacent track.

        Args:
            df (pd.DataFrame): The dataframe to be used (full track_df or subset lineage_df).
            node_id (str): The current node ID to get the next from.
            forward (bool, optional): If true, pick the next track (right/down).
                Otherwise, pick the previous track (left/up). Defaults to True.
        """
        # Determine which axis to use for finding neighbors
        axis_label = "area" if self.feature == "area" else "x_axis_pos"

        if df.empty:
            return None
        node_data = df.loc[df["node_id"] == node_id]
        if node_data.empty:
            return None

        # Fetch the axis value for the given node ID
        axis_label_value = node_data[axis_label].iloc[0]
        t = node_data["t"].iloc[0]

        if forward:
            neighbors = df.loc[
                (df[axis_label] > axis_label_value) & (df["t"] == t)
            ]
        else:
            neighbors = df.loc[
                (df[axis_label] < axis_label_value) & (df["t"] == t)
            ]
        if not neighbors.empty:
            # Find the closest index label
            closest_index_label = (
                (neighbors[axis_label] - axis_label_value).abs().idxmin()
            )
            neighbor = neighbors.loc[closest_index_label, "node_id"]
            return neighbor

    def get_predecessor(self, node_id: str) -> str | None:
        """Get the predecessor node of the given node_id

        Args:
            node_id (str): the node id to get the predecessor of

        Returns:
            str | None: THe node id of the predecessor, or none if no predecessor
            is found
        """
        parent_id = self.track_df.loc[
            self.track_df["node_id"] == node_id, "parent_id"
        ].values[0]
        parent_row = self.track_df.loc[self.track_df["node_id"] == parent_id]
        if not parent_row.empty:
            return parent_row["node_id"].values[0]

    def get_successor(self, node_id: str) -> str | None:
        """Get the successor node of the given node_id. If there are two children,
        picks one arbitrarily.

        Args:
            node_id (str): the node id to get the successor of

        Returns:
            str | None: THe node id of the successor, or none if no successor
            is found
        """
        children = self.track_df.loc[self.track_df["parent_id"] == node_id]
        if not children.empty:
            child = children.to_dict("records")[0]
            return child["node_id"]
