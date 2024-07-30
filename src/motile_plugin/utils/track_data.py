import pandas as pd
from psygnal import Signal
from PyQt5.QtCore import QObject


class TrackData(QObject):
    """Keeps track of the node data in a pandas dataframe. Send signal upon updates"""

    data_updated = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.df = pd.DataFrame()

    def _update_data(self, df: pd.DataFrame):
        """Replace the dataframe with a new dataframe"""
        self.df = df
        print(df)

    def _set_fork(self, node_id: str):
        """Set the node with this id to fork and send a signal to emit the update"""

        self.df.loc[self.df["node_id"] == node_id, "symbol"] = "triangle_up"
        self.df.loc[self.df["node_id"] == node_id, "state"] = "fork"
        self.df.loc[self.df["node_id"] == node_id, "annotated"] = True

        self.data_updated.emit(node_id, "fork")

    def _set_endpoint(self, node_id: str):
        """Set the node with this id to endpoint and send a signal to emit the update"""

        self.df.loc[self.df["node_id"] == node_id, "symbol"] = "x"
        self.df.loc[self.df["node_id"] == node_id, "state"] = "endpoint"
        self.df.loc[self.df["node_id"] == node_id, "annotated"] = True

        self.data_updated.emit(node_id, "endpoint")

    def _reset_node(self, node_id: str):
        """Set the node with this id to endpoint and send a signal to emit the update"""

        self.df.loc[self.df["node_id"] == node_id, "symbol"] = "disc"
        self.df.loc[self.df["node_id"] == node_id, "state"] = (
            "intermittent"  # replace with NodeAttr.STATE.value
        )
        self.df.loc[self.df["node_id"] == node_id, "annotated"] = False

        self.data_updated.emit(node_id, "intermittent")
