from motile_plugin.backend.solver_params import SolverParams
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ParamView(QWidget):
    def __init__(self, param_name: str, solver_params: SolverParams):
        super().__init__()
        self.param_name = param_name
        title = QLabel(solver_params.model_fields[param_name].title)
        self.param_value = QLabel()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title)
        layout.addWidget(self.param_value)
        self.setLayout(layout)

        self.update_from_params(solver_params)

    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is not None:
            self.show()
            text = (
                str(param_val)
                if isinstance(param_val, int)
                else f"{param_val:.1f}"
            )
            self.param_value.setText(text)
        else:
            self.hide()


class SolverParamsViewer(QWidget):
    """ Widget for viewing SolverParams. To update for a backend change to 
    SolverParams, emit the new_params signal, which Labels will connect to and 
    use to update the UI.
    """
    new_params = Signal(SolverParams)

    def __init__(self, solver_params: SolverParams):
        super().__init__()
        self.solver_params = solver_params
        self.param_categories = {
            "hyperparams": ["max_edge_distance", "max_children"],
            "costs": [
                "appear_cost",
                "division_cost",
                "disappear_cost",
                "distance_weight",
                "distance_offset",
                "iou_weight",
                "iou_offset",
            ],
        }
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._ui_params_group(title="Hyperparameters", param_category="hyperparams"))
        main_layout.addWidget(self._ui_params_group(title="Costs", param_category="costs"))
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

    def _ui_params_group(self, title, param_category) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout()
        for param_name in self.param_categories[param_category]:
            label = self._param_view(param_name)
            layout.addWidget(label)
        group.setLayout(layout)
        return group

    def _param_view(self, param_name) -> ParamView:
        """Helper function to 

        Args:
            param_name (_type_): _description_

        Returns:
            ParamView: _description_
        """
        
        param_label = ParamView(param_name, self.solver_params)
        param_label.update_from_params(self.solver_params)
        self.new_params.connect(param_label.update_from_params)
        return param_label
