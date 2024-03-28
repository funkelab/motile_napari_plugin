from functools import partial

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .solver_params import SolverParams


class ParamSpinBox(QSpinBox):
    send_value = Signal(object)
    def __init__(self, param_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.param_name = param_name
        # whenever we update the value of the spinbox, emit the send value signal
        # necessary to have custom signal that is also emitted when checkboxes are
        # checked, without changing the spinbox value
        self.valueChanged.connect(self.send_value.emit)
    
    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is not None:
            self.setValue(param_val)
    
    def toggle_enable(self, checked: bool):
        if checked:
            self.enable()
        else:
            self.disable()


class ParamDoubleSpinBox(QDoubleSpinBox):
    send_value = Signal(object)
    def __init__(self, param_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.param_name = param_name
        # whenever we update the value of the spinbox, emit the send value signal
        # necessary to have custom signal that is also emitted when checkboxes are
        # checked, without changing the spinbox value
        self.valueChanged.connect(self.send_value.emit)

    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is not None:
            self.setValue(param_val)
    
    def toggle_enable(self, checked: bool):
        if checked:
            self.setEnabled(True)
            self.send_value.emit(self.value())
        else:
            self.setEnabled(False)
            self.send_value.emit(None)

class ParamCheckBox(QCheckBox):
    def __init__(self, param_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.param_name = param_name
    
    def update_from_params(self, params: SolverParams):
        param_val = params.__getattribute__(self.param_name)
        if param_val is None:
            self.setChecked(False)
    

class ParamCheckGroup(QGroupBox):
    def __init__(self, param_names, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.param_names = param_names

    def update_from_params(self, params: SolverParams):
        param_vals = [params.__getattribute__(name) for name in self.param_names]
        if all([v is None for v in param_vals]):
            self.setChecked(False)


class SolverParamsWidget(QWidget):
    new_params = Signal(SolverParams)
    """ Widget for viewing and editing SolverParams. 
    Spinboxes will be created for each parameter in SolverParams and linked such that 
    editing the value in the spinbox will change the corresponding parameter. 
    Checkboxes will also  be created for each optional parameter (group) and linked such
    that unchecking the box will update the parameter value to None, and checking will 
    update the parameter to the current spinbox value.
    If editable is false, the whole widget will be disabled.
    To update for a backend change to SolverParams, create a new Widget with the
    new params.
    """
    def __init__(self, solver_params: SolverParams, editable=False):
        super().__init__()
        self.solver_params = solver_params
        self.editable = editable
        self.param_categories = {
            "data_params": ["max_edge_distance",  "max_children", "max_parents"],
            "constant_costs": ["appear_cost", "division_cost", "disappear_cost", "merge_cost"],
            "variable_costs": ["distance", "iou",],
        }
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._ui_data_specific_hyperparameters())
        main_layout.addWidget(self._ui_constant_costs())
        for group in self._ui_variable_costs():
            main_layout.addWidget(group)
        self.setLayout(main_layout)
        self.setEnabled(self.editable)

    def _ui_data_specific_hyperparameters(self) -> QGroupBox:
        # Data-specific Hyperparameters section
        hyperparameters_group = QGroupBox("Data-Specific Hyperparameters")
        hyperparameters_layout = QFormLayout()
        for param_name in self.param_categories["data_params"]:
            field = self.solver_params.model_fields[param_name]
            spinbox = self._param_spinbox(param_name, negative=False)
            self._add_form_row(hyperparameters_layout, field.title, spinbox, tooltip=field.description)
        hyperparameters_group.setLayout(hyperparameters_layout)
        return hyperparameters_group

    def _ui_constant_costs(self) -> QGroupBox:
        # Constant Costs section
        constant_costs_group = QGroupBox("Constant Costs")
        constant_costs_layout = QVBoxLayout()
        for param_name in self.param_categories["constant_costs"]:
            layout = QHBoxLayout()
            field = self.solver_params.model_fields[param_name]
            spinbox = self._param_spinbox(param_name, negative=False)
            checkbox = ParamCheckBox(param_name, field.title)
            checkbox.setToolTip(field.description)
            checkbox.setChecked(True)
            checkbox.toggled.connect(spinbox.toggle_enable)
            self.new_params.connect(checkbox.update_from_params)
            layout.addWidget(checkbox)
            layout.addWidget(spinbox)
            constant_costs_layout.addLayout(layout)

        constant_costs_group.setLayout(constant_costs_layout)
        return constant_costs_group

    def _ui_variable_costs(self) -> list[QGroupBox]:
        groups = []
        for param_type in self.param_categories["variable_costs"]:
            title = f"{param_type.title()} Cost"
            group_tooltip = f"Use the {param_type.title()} between objects as a linking feature."
            param_names = [f"{param_type}_weight", f"{param_type}_offset"]
            groups.append(self._create_feature_cost_group(
                title,
                param_names=param_names,
                checked=True,
                group_tooltip=group_tooltip,
            ))
        return groups

    def _create_feature_cost_group(
        self,
        title,
        param_names,
        checked=True,
        group_tooltip=None,
    ) -> ParamCheckGroup:
        feature_cost = ParamCheckGroup(param_names, title)
        feature_cost.setCheckable(True)
        feature_cost.setChecked(checked)
        feature_cost.setToolTip(group_tooltip)
        self.new_params.connect(feature_cost.update_from_params)
        layout = QFormLayout()
        for param_name in param_names:
            field = self.solver_params.model_fields[param_name]
            spinbox = self._param_spinbox(param_name, negative=True)
            feature_cost.toggled.connect(spinbox.toggle_enable)
            self._add_form_row(layout, field.title, spinbox, tooltip=field.description)
        feature_cost.setLayout(layout)
        return feature_cost

    def _param_spinbox(self, param_name, negative=False) -> QWidget:
        """Create a double spinbox with one decimal place and link to solver param.

        Args:
            default_val (_type_): The default value to use in the spinbox
            negative (bool, optional): Whether to allow negative values in the spinbox.
                Defaults to False.

        Returns:
            ParamSpinbox | ParamDouble: A spinbox linked to the solver param with the given name
        """

        field = self.solver_params.model_fields[param_name]
        # using subclass to allow Optional annotations. Might lead to strange behavior
        # if annotated with more than one (non-None) type
        if issubclass(int, field.annotation):
            spinbox = ParamSpinBox(param_name)
        elif issubclass(float, field.annotation):
            spinbox = ParamDoubleSpinBox(param_name)
            spinbox.setDecimals(1)
        else:
            raise ValueError(f"Expected dtype int or float, got {field.annotation}")
        max_val = 10000
        if negative:
            min_val = -1 * max_val
        else:
            min_val = 0
        spinbox.setRange(min_val, max_val)
        curr_val = self.solver_params.__getattribute__(param_name)
        if curr_val is None:
            curr_val = field.get_default()
        spinbox.setValue(curr_val)
        spinbox.send_value.connect(
            partial(self.solver_params.__setattr__, param_name)
        )
        self.new_params.connect(spinbox.update_from_params)
        return spinbox

    def _add_form_row(self, layout: QFormLayout, label, value, tooltip=None):
        layout.addRow(label, value)
        row_widget = layout.itemAt(layout.rowCount() - 1, QFormLayout.LabelRole).widget()
        row_widget.setToolTip(tooltip)
