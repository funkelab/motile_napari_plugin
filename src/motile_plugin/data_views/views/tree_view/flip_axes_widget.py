from psygnal import Signal
from qtpy.QtWidgets import QGroupBox, QPushButton, QVBoxLayout, QWidget


class FlipTreeWidget(QWidget):
    """Widget to flip the axis of the tree view"""

    flip_tree = Signal()

    def __init__(self):
        super().__init__()

        flip_layout = QVBoxLayout()
        display_box = QGroupBox("Plot axes [F]")
        flip_button = QPushButton("Flip")
        flip_button.clicked.connect(self.flip)
        flip_layout.addWidget(flip_button)
        display_box.setLayout(flip_layout)

        layout = QVBoxLayout()
        layout.addWidget(display_box)
        self.setLayout(layout)
        display_box.setMaximumWidth(90)
        display_box.setMaximumHeight(82)

    def flip(self):
        """Send a signal to flip the axes of the plot"""

        self.flip_tree.emit()
