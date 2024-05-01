from motile_plugin.backend.solver_params import CompoundSolverParam, SolverParams
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox
)
from abc import ABC
from typing import Any


# This is just an interface
class ParamValueWidget(QWidget):
    valueChanged = Signal(object)
    
    def update_value(self, value: Any) -> None:
        raise NotImplementedError()

    def get_value(self) -> Any:
        raise NotImplementedError()

class ParamValueLabel(QLabel):
    valueChanged = Signal(object)
    def update_value(self, value: int | float | None) -> None:
        if value is not None:
            text = (
                    str(value)
                    if isinstance(value, int)
                    else f"{value:.1f}"
                )
            self.setText(text)
    
    def get_value(self) -> Any:
        return self.text()

class ParamValueSpinbox(QDoubleSpinBox):
    def __init__(self, dtype, negative: bool = True) -> None:
        super().__init__()
        if issubclass(int, dtype):
            self.setDecimals(0)
        elif issubclass(float, dtype):
            self.setDecimals(1)
        else:
            raise ValueError(
                f"Expected dtype int or float, got {dtype}"
            )
        max_val = 10000
        min_val = -1 * max_val if negative else 0
        self.setRange(min_val, max_val)
    
    def update_value(self, value: int | float | None) -> None:
        if value is not None:
            self.setValue(value)

    def get_value(self) -> Any:
        return self.value()


class CompoundParamValue(ParamValueWidget):
    def __init__(self, weight_widget: ParamValueWidget, offset_widget: ParamValueWidget):
        super().__init__()
        self.weight = weight_widget
        self.offset = offset_widget
        self.weight.valueChanged.connect(lambda: self.valueChanged.emit(
            self.get_value()))
        self.offset.valueChanged.connect(lambda: self.valueChanged.emit(
            self.get_value()))

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("weight:"))
        layout.addWidget(self.weight)
        layout.addWidget(QLabel("offset:"))
        layout.addWidget(self.offset)
        self.setLayout(layout)
    
    def update_value(self, value: CompoundSolverParam) -> None:
        self.weight.update_value(value.weight)
        self.offset.update_value(value.offset)
    
    def get_value(self) -> Any:
        return CompoundSolverParam(
            weight=self.weight.get_value(), offset=self.offset.get_value()
        )

