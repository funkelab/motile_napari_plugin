from __future__ import annotations

from typing import TYPE_CHECKING

from motile_toolbox.candidate_graph import NodeAttr
from pydantic import BaseModel

if TYPE_CHECKING:
    import networkx as nx
    import numpy as np


class Tracks(BaseModel):
    graph: nx.DiGraph
    segmentation: np.ndarray | None = None
    time_attr: str = NodeAttr.TIME.value
    pos_attr: str = NodeAttr.POS.value
    # pydantic does not check numpy arrays
    model_config = {"arbitrary_types_allowed": True}

    def get_location(self, node, incl_time=False):
        data = self.graph.nodes[node]
        if isinstance(self.pos_attr, (tuple, list)):
            pos = [data[dim] for dim in self.pos_attr]
        else:
            pos = data[self.pos_attr]

        if incl_time:
            pos = [data[self.time_attr], *pos]

        return pos
