from pydantic import BaseModel, Field

class CompoundSolverParam(BaseModel):
    weight: float = Field(
        1,
        title="Weight",
        description=r"""Value multiplied by attribute to create the cost for selecting an edge.
The weight should be positive when the attribute is already a cost (higher is worse)
and negative when a higher value is better.
The magnitude of the weight helps balance this cost with other costs.""",
    )
    offset: float = Field(
        -20,
        title="Offset",
        description=r"""Value added to (attr * weight) to create the cost for selecting an edge.
A negative offset encourages selecting more edges.
(If all costs are positive, the optimal solution is selecting nothing.)""",
    )

class SolverParams(BaseModel):
    """The set of solver parameters supported in the motile plugin.
    Used to build the UI as well as store parameters for runs.
    """

    max_edge_distance: float = Field(
        50.0,
        title="Max Move Distance",
        description=r"""The maximum distance an object center can move between time frames.
Objects further than this cannot be matched, but making this value larger will increase solving time.""",
    )
    max_children: int = Field(
        2,
        title="Max Children",
        description="The maximum number of object in time t+1 that can be linked to an item in time t.\nIf no division, set to 1.",
    )
    appear_cost: float | None = Field(
        30,
        title="Appear Cost",
        description=r"""Cost for starting a new track. A higher value means fewer selected tracks and fewer merges.""",
    )
    disappear_cost: float | None = Field(
        30,
        title="Disappear Cost",
        description=r"""Cost for ending a track. A higher value means fewer selected tracks and fewer divisions.""",
    )
    division_cost: float | None = Field(
        20,
        title="Division Cost",
        description=r"""Cost for a track dividing. A higher value means fewer divisions.
If this cost is higher than the appear cost, tracks will likely never divide.""",
    )
    distance: CompoundSolverParam | None = Field(
        CompoundSolverParam(weight=1, offset=-20),
        title="Distance",
        description=r"""Use the distance between objects as a feature for selecting tracks.""",
    )
    iou: CompoundSolverParam | None = Field(
        CompoundSolverParam(weight=5, offset=0),
        title="IOU",
        description=r"""Use the intersection over union between objects as a feature for selecting tracks.""",
    )
