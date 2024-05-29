""" A module for widgets that hold parameter values. Each of these
widgets implements the following interface:

class ParamValue(QWidget):
    valueChanged = Signal(object)

    def update_value(self, value: Any) -> None:
        raise NotImplementedError()

    def get_value(self) -> Any:
        raise NotImplementedError

This "interface" is only enforced by duck typing, as is the pythonic way.
"""

from qtpy.QtCore import Signal
from qtpy.QtWidgets import QDoubleSpinBox, QLabel


class StaticParamValue(QLabel):
    """A widget for holding a parameter value (int or float) that cannot be
    changed from the UI. The valueChanged signal is just to fit my interface
    so that the compound widget can treat the static and editable children
    the same.
    """

    valueChanged = Signal(object)

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
    valueChanged = Signal(object)

    def __init__(self, dtype: type, negative: bool = True) -> None:
        """A widget for holding an editable parameter value (int or float).
        The valueChanged signal is overriden from the QDoubleSpinbox
        to allow emitting NoneType.

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
        super().valueChanged.connect(self.valueChanged.emit)

    def update_value(self, value: int | float | None) -> None:
        if value is not None:
            self.setValue(value)

    def get_value(self) -> int | float:
        return self.value()
