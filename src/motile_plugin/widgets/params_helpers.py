from motile_plugin.backend.solver_params import CompoundSolverParam
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
)


class StaticParamValue(QLabel):
    """A widget for holding a parameter value (int or float) that cannot be
    changed from the UI. It does not implement valueChanged (as the other
    param value widgets do in my pseudo-interface implementation)
    because that is intended to be emitted when changes are made from the UI.
    """

    def update_value(self, value: int | float | None) -> None:
        if value is not None:
            text = str(value) if isinstance(value, int) else f"{value:.1f}"
            self.setText(text)

    def get_value(self) -> int | float:
        try:
            return int(self.text())
        except ValueError:
            return float(self.text())


class EditableParamValue(QDoubleSpinBox):
    def __init__(self, dtype: type, negative: bool = True) -> None:
        """A widget for holding an editable parameter value (int or float).
        The valueChanged signal is inherited from the QDoubleSpinbox.

        Args:
            dtype (type): The data type (int or float) of the parameter
            negative (bool, optional): Whether the value can be negative.
                Defaults to True.

        Raises:
            ValueError: If dtype is not (a superclass of) int or float.
        """
        super().__init__()
        if issubclass(int, dtype):
            self.setDecimals(0)
        elif issubclass(float, dtype):
            self.setDecimals(1)
        else:
            raise ValueError(f"Expected dtype int or float, got {dtype}")
        max_val = 10000
        min_val = -1 * max_val if negative else 0
        self.setRange(min_val, max_val)

    def update_value(self, value: int | float | None) -> None:
        if value is not None:
            self.setValue(value)

    def get_value(self) -> int | float:
        return self.value()


class CompoundParamValue:
    valueChanged = Signal(CompoundSolverParam)

    def __init__(
        self,
        weight_widget: StaticParamValue | EditableParamValue,
        const_widget: StaticParamValue | EditableParamValue,
    ):
        """A widget to hold the value of a compound solver parameter (one that
        has weight and offset). This also implements the same interface as
        its component widgets for easy interchangability.

        Args:
            weight_widget (StaticParamValue | EditableParamValue): a widget
                holding the weight of the compound parameter
            offset_widget (StaticParamValue | EditableParamValue): a widget
                holding the offset of the compound parameter
        """
        super().__init__()
        self.weight = weight_widget
        self.constant = const_widget
        self.weight.valueChanged.connect(
            lambda: self.valueChanged.emit(self.get_value())
        )
        self.constant.valueChanged.connect(
            lambda: self.valueChanged.emit(self.get_value())
        )

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        weight_label = QLabel("weight:")
        weight_label.setToolTip(
            CompoundSolverParam.model_fields["weight"].description
        )
        layout.addWidget(weight_label, 0, 0)
        layout.addWidget(self.weight, 0, 1)
        constant_label = QLabel("constant:")
        layout.addWidget(constant_label, 1, 0)
        constant_label.setToolTip(
            CompoundSolverParam.model_fields["constant"].description
        )
        layout.addWidget(self.constant, 1, 1)
        self.setLayout(layout)

    def update_value(self, value: CompoundSolverParam) -> None:
        self.weight.update_value(value.weight)
        self.constant.update_value(value.constant)

    def get_value(self) -> CompoundSolverParam:
        return CompoundSolverParam(
            weight=self.weight.get_value(), constant=self.constant.get_value()
        )
