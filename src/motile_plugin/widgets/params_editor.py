from functools import partial
from types import NoneType

from motile_plugin.backend.solver_params import SolverParams, CompoundSolverParam
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QAbstractSpinBox,
    QPushButton,
)
from .params_viewer import ParamView
from .params_helpers import ParamValueWidget, CompoundParamValue, ParamValueSpinbox


class ParamEdit(QWidget):
    send_value = Signal(object)

    def __init__(self, param_name: str, solver_params: SolverParams, negative: bool = False):
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
        self.negative = negative
        self.param_label = self._param_label_widget()
        self.param_label.setToolTip(field.description)
        self.param_value: ParamValueWidget = self._param_value_widget()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.param_label)
        layout.addWidget(self.param_value)
        self.setLayout(layout)

        self.update_from_params(solver_params)

    def _param_label_widget(self) -> QLabel:
        return QLabel(self.title)
    
    def _param_value_widget(self) -> ParamValueWidget:
        if issubclass(CompoundSolverParam, self.dtype):
            return CompoundParamValue(ParamValueSpinbox(float, self.negative), ParamValueSpinbox(float, self.negative))
        else:
            return ParamValueSpinbox(float, self.negative)

    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is None:
            raise ValueError("Got None value for required field {self.param_name} with dtype {self.dtype}")
        else:
            self.param_value.update_value(param_val)

class OptionalParamEdit(ParamEdit):
    def __init__(self, param_name: str, solver_params: SolverParams, negative: bool = False):
        super().__init__(param_name, solver_params, negative)
        self.param_label.toggled.connect(self.toggle_enable)
        # whenever we update the value of the spinbox, emit the send value signal
        # necessary to have custom signal that is also emitted when checkboxes are
        # checked, without changing the spinbox value
        self.param_value.valueChanged.connect(self.send_value.emit)

    def _param_label_widget(self) -> QCheckBox:
        return QCheckBox(self.title)
    
    def update_from_params(self, params: SolverParams):
        super().update_from_params(params)
        param_val = params.__getattribute__(self.param_name)
        if param_val is None:
            self.param_label.setChecked(False)
            self.param_value.setEnabled(False)
        else:
            self.param_label.setChecked(True)
            self.param_value.setEnabled(True)
    
    def toggle_enable(self, checked: bool):
        value = self.param_value.get_value() if checked else None
        self.send_value.emit(value)
        self.param_value.setEnabled(checked)


class SolverParamsEditor(QWidget):
    """ Widget for editing SolverParams.
    Spinboxes will be created for each parameter in SolverParams and linked such that
    editing the value in the spinbox will change the corresponding parameter.
    Checkboxes will also  be created for each optional parameter (group) and linked such
    that unchecking the box will update the parameter value to None, and checking will
    update the parameter to the current spinbox value.
    To update for a backend change to SolverParams, emit the new_params signal,
    which the spinboxes and checkboxes will connect to and use to update the
    UI and thus the stored solver params.
    """
    new_params = Signal(SolverParams)

    def __init__(self):
        super().__init__()
        self.solver_params = SolverParams()
        self.param_categories = {
            "hyperparams": ["max_edge_distance", "max_children"],
            "costs": [
                "appear_cost",
                "division_cost",
                "disappear_cost",
                "distance",
                "iou",
            ],
        }

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        debug_button = QPushButton("Print params")
        debug_button.clicked.connect(lambda: print(self.solver_params))
        main_layout.addWidget(debug_button)
        main_layout.addWidget(self._params_group("Hyperparameters", "hyperparams", negative=False))
        main_layout.addWidget(self._params_group("Costs", "costs", negative=True))
        #for group in self._ui_variable_costs():
            #main_layout.addWidget(group)
        self.setLayout(main_layout)

    def _params_group(self, title: str, param_category: str, negative: bool) -> QWidget:
        """A widget for setting the parameters of the run.

        Returns:
            QWidget: 
        """
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(title))
        for param_name in self.param_categories[param_category]:
            field = self.solver_params.model_fields[param_name]
            param_cls = OptionalParamEdit if issubclass(NoneType, field.annotation) else ParamEdit
            param_row = param_cls(param_name, self.solver_params, negative=negative)
            param_row.send_value.connect(
                partial(self.solver_params.__setattr__, param_name)
            )
            self.new_params.connect(param_row.update_from_params)
            param_row.setToolTip(field.description)
            layout.addWidget(param_row)
        widget.setLayout(layout)
        return widget
