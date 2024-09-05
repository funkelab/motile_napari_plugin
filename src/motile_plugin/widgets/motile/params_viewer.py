from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from motile_plugin.backend.solver_params import SolverParams

from .param_values import StaticParamValue


class ParamView(QWidget):
    def __init__(self, param_name: str, solver_params: SolverParams):
        """A widget for viewing a parameter (read only). Can be updated from
        the backend by calling update_from_params with a new SolverParams
        object.

        Args:
            param_name (str): The name of the parameter to view in this UI row.
                Must correspond to one of the attributes of SolverParams.
            solver_params (SolverParams): The SolverParams object to use to
                initialize the view. Provides the title to display and the
                initial value.
        """
        super().__init__()
        self.param_name = param_name
        field = solver_params.model_fields[param_name]
        self.dtype = field.annotation
        self.title = field.title
        self.param_label = QLabel(self.title)
        self.param_label.setToolTip(field.description)
        self.param_value = StaticParamValue()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.param_label)
        layout.addWidget(self.param_value)
        self.setLayout(layout)

        self.update_from_params(solver_params)

    def update_from_params(self, params: SolverParams):
        """Updates the current parameter value displayed in self.param_value,
        or hides the whole row if the value is None.

        Args:
            params (SolverParams): The solver parameters we use to update
                the UI. This object uses self.param_name to know which value
                to retrieve.
        """
        param_val = params.__getattribute__(self.param_name)
        if param_val is not None:
            self.param_value.update_value(param_val)
            self.show()
        else:
            self.hide()


class SolverParamsViewer(QWidget):
    """Widget for viewing SolverParams. To update for a backend change to
    SolverParams, emit the new_params signal, which each parameter label
    will connect to and use to update the UI.
    """

    new_params = Signal(SolverParams)

    def __init__(self):
        super().__init__()
        self.solver_params = SolverParams()
        self.param_categories = {
            "hyperparams": ["max_edge_distance", "max_children"],
            "constant_costs": [
                "edge_selection_cost",
                "appear_cost",
                "division_cost",
            ],
            "attribute_costs": [
                "distance_cost",
                "iou_cost",
            ],
        }
        main_layout = QVBoxLayout()
        main_layout.addWidget(
            self._params_group(
                title="Hyperparameters", param_category="hyperparams"
            )
        )
        main_layout.addWidget(
            self._params_group(
                title="Constant Costs", param_category="constant_costs"
            )
        )
        main_layout.addWidget(
            self._params_group(
                title="Attribute Weights", param_category="attribute_costs"
            )
        )
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

    def _params_group(self, title: str, param_category: str) -> QGroupBox:
        """A helper function to create a group of parameters in the UI.
        Also connects each parameter to the self.new_params signal so the
        values can be updated when new parameters are viewed.

        Args:
            title (str): The title to put at the top of the group
            param_category (str): A key of self.param_categories used to
                get the list of parameters in this group.

        Returns:
            QGroupBox: A widget containing all the parameters in the group,
                with static titles and values that can be updated via emitting
                the self.new_params signal.
        """
        group = QGroupBox(title)
        layout = QVBoxLayout()
        for param_name in self.param_categories[param_category]:
            param_view = ParamView(param_name, self.solver_params)
            self.new_params.connect(param_view.update_from_params)
            layout.addWidget(param_view)
        group.setLayout(layout)
        return group
