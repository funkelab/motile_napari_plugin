from psygnal import Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class TreeViewFeatureWidget(QWidget):
    """Widget to switch between viewing all nodes versus nodes of one or more lineages in the tree widget"""

    change_feature = Signal(str)

    def __init__(self):
        super().__init__()

        self.feature = "tree"

        display_box = QGroupBox("Feature [A]")
        display_layout = QHBoxLayout()
        button_group = QButtonGroup()
        self.show_tree_radio = QRadioButton("Lineage Tree")
        self.show_tree_radio.setChecked(True)
        self.show_tree_radio.clicked.connect(lambda: self._set_feature("tree"))
        self.show_area_radio = QRadioButton("Object size")
        self.show_area_radio.clicked.connect(lambda: self._set_feature("area"))
        button_group.addButton(self.show_tree_radio)
        button_group.addButton(self.show_area_radio)
        display_layout.addWidget(self.show_tree_radio)
        display_layout.addWidget(self.show_area_radio)
        display_box.setLayout(display_layout)
        display_box.setMaximumWidth(250)

        layout = QVBoxLayout()
        layout.addWidget(display_box)

        self.setLayout(layout)

    def _toggle_feature_mode(self, event=None) -> None:
        """Toggle display mode"""

        if self.show_area_radio.isEnabled: # if button is disabled, toggle is not allowed
            if self.feature == "area":
                self._set_feature("tree")
                self.show_tree_radio.setChecked(True)
            else:
                self._set_feature("area")
                self.show_area_radio.setChecked(True)

    def _set_feature(self, mode: str):
        """Emit signal to change the display mode"""

        self.feature = mode
        self.change_feature.emit(mode)
