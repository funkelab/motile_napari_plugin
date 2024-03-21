
from motile import Solver, TrackGraph
from motile.constraints import MaxChildren, MaxParents
from motile.costs import EdgeSelection, Appear, Split, Disappear
from motile_toolbox.candidate_graph import graph_from_segmentation, graph_to_nx, NodeAttr, EdgeAttr
import logging
import time
from .solver_params import SolverParams
from .run import Run

logger = logging.getLogger(__name__)


class MotileSolver():
    def __init__(self, solver_params: SolverParams):
        self.params = solver_params

    def solve(
        self,
        segmentation,
        position_keys,
        ):
        edge_attributes = []
        if self.params.distance_weight is not None:
            edge_attributes.append(EdgeAttr.DISTANCE)
        if self.params.iou_weight is not None:
            edge_attributes.append(EdgeAttr.IOU)
        cand_graph = graph_from_segmentation(
            segmentation, 
            self.params.max_edge_distance,
            node_attributes=(NodeAttr.SEG_ID,),
            edge_attributes=edge_attributes,
            position_keys=position_keys,
        )
        logger.debug(f"Cand graph has {cand_graph.number_of_nodes()} nodes")

        solver = Solver(TrackGraph(cand_graph))
        solver.add_constraints(MaxChildren(self.params.max_children))
        solver.add_constraints(MaxParents(self.params.max_parents))

        if self.params.appear_cost is not None:        
            solver.add_costs(Appear(self.params.appear_cost))
        if self.params.disappear_cost is not None:
            solver.add_costs(Disappear(self.params.disappear_cost))
        if self.params.division_cost is not None:
            solver.add_costs(Split(constant=self.params.division_cost))
        if self.params.merge_cost is not None:
            from motile.costs import Merge
            solver.add_costs(Merge(constant=self.params.merge_cost))

        if self.params.distance_weight is not None:
            solver.add_costs(EdgeSelection(
                self.params.distance_weight,
                attribute=EdgeAttr.DISTANCE.value,
                constant=self.params.distance_offset), name="distance")
        if self.params.iou_weight is not None:
            solver.add_costs(EdgeSelection(
                weight=self.params.iou_weight, 
                attribute=EdgeAttr.IOU.value,
                constant=self.params.iou_offset), name="iou")

        start_time = time.time()
        solution = solver.solve(verbose=True)
        logger.info(f"Solution took {time.time() - start_time} seconds")

        solution_graph = solver.get_selected_subgraph(solution=solution)
        solution_nx_graph = graph_to_nx(solution_graph)
        
        return solution_nx_graph