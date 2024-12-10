from psygnal import Signal
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QWidget


class FlipTreeWidget(QWidget):
    """Widget to flip the axis of the tree view"""

    flip_tree = Signal()

    def __init__(self):
        super().__init__()

        flip_layout = QHBoxLayout()
        flip_button = QPushButton("Flip axes [F]")
        flip_button.clicked.connect(self.flip)
        flip_layout.addWidget(flip_button)

        self.setLayout(flip_layout)

    def flip(self):
        """Send a signal to flip the axes of the plot"""

        self.flip_tree.emit()
