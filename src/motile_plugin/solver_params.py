
from pydantic import Field, BaseModel


class SolverParams(BaseModel):
    max_edge_distance: float = Field(
        50.0, 
        title="Max Move Distance", 
        description=r"""The maximum distance an object center can move between time frames.
Objects further than this cannot be matched, but making this value larger will increase solving time."""
    )
    max_children: int = Field(
        2,
        title="Max Children",
        description="The maximum number of object in time t+1 that can be linked to an item in time t.\nIf no division, set to 1."
    )
    max_parents: int = Field(
        1,
        title="Max Parent",
        description=r"""The maximum number of object in time t that can be linked to an item in time t+1.
If no merging, set to 1."""
    )
    appear_cost: float | None = Field(
        30,
        title="Appear Cost",
        description=r"""Cost for starting a new track. A higher value means fewer selected tracks and fewer merges."""
    )
    disappear_cost: float | None = Field(
        30,
        title="Disappear Cost",
        description=r"""Cost for ending a track. A higher value means fewer selected tracks and fewer divisions."""
    )
    division_cost: float | None = Field(
        20,
        title="Division Cost",
        description=r"""Cost for a track dividing. A higher value means fewer divisions.
If this cost is higher than the appear cost, tracks will likely never divide."""
    )
    merge_cost: float | None = Field(
        20,
        title="Merge Cost",
        description=r"""Cost for a track merging. A higher value means fewer merges.
If this cost is higher than the disappear cost, tracks will likely never merge."""
    )
    distance_weight: float | None = Field(
        1,
        title="Distance Weight",
        description=r"""Value multiplied by distance to create the cost for selecting an edge.
The weight should generally be positive, because a higher distance should be a higher cost.
The magnitude of the weight helps balance distance with other costs."""
    )
    distance_offset: float | None = Field(
        -20,
        title="Distance Offset",
        description=r"""Value added to (distance * weight) to create the cost for selecting an edge.
Usually should be negative to encourage anything being selected.
(If all costs are positive, the optimal solution is selecting nothing.)"""
    )
    iou_weight: float | None = Field(
        -5,
        title="IOU Weight",
        description=r"""Value multiplied by IOU to create cost.
The weight should generally be negative, because a higher IOU should be a lower cost.
The magnitude of the weight helps balance IOU with other costs."""
    )
    iou_offset: float | None = Field(
        0,
        title="IOU Offset",
        description=r"""Value added to (IOU * weight) to create cost.
Zero is a sensible default with a negative weight, and will have the cost range from -weight to 0
(In this case, any IOU will never hurt selection)."""
    )