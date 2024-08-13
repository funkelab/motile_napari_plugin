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
