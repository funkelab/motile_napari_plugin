from psygnal import Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class TreeViewModeWidget(QWidget):
    """Widget to switch between viewing all nodes versus nodes of one or more lineages in the tree widget"""

    change_mode = Signal(str)

    def __init__(self):
        super().__init__()

        self.mode = "all"

        display_box = QGroupBox("Display [L]")
        display_layout = QHBoxLayout()
        button_group = QButtonGroup()
        self.show_all_radio = QRadioButton("All cells")
        self.show_all_radio.setChecked(True)
        self.show_all_radio.clicked.connect(lambda: self._set_mode("all"))
        self.show_lineage_radio = QRadioButton("Current lineage(s)")
        self.show_lineage_radio.clicked.connect(
            lambda: self._set_mode("lineage")
        )
        button_group.addButton(self.show_all_radio)
        button_group.addButton(self.show_lineage_radio)
        display_layout.addWidget(self.show_all_radio)
        display_layout.addWidget(self.show_lineage_radio)
        display_box.setLayout(display_layout)
        display_box.setMaximumWidth(250)

        layout = QVBoxLayout()
        layout.addWidget(display_box)

        self.setLayout(layout)

    def _toggle_display_mode(self, event=None) -> None:
        """Toggle display mode"""

        if self.mode == "lineage":
            self._set_mode("all")
            self.show_all_radio.setChecked(True)
        else:
            self._set_mode("lineage")
            self.show_lineage_radio.setChecked(True)

    def _set_mode(self, mode: str):
        """Emit signal to change the display mode"""

        self.mode = mode
        self.change_mode.emit(mode)
