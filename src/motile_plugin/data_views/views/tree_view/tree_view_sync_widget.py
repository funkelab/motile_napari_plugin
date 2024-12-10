from qtpy.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QWidget,
)


class SyncWidget(QWidget):
    """Widget to switch between viewing all nodes versus nodes of one or more lineages in the tree widget"""

    def __init__(self):
        super().__init__()

        sync_layout = QHBoxLayout()
        self.sync_button = SyncButton()
        sync_layout.addWidget(self.sync_button)
        self.setLayout(sync_layout)


class SyncButton(QPushButton):
    def __init__(self):
        super().__init__()

        self.setCheckable(True)
        self.setText("Sync Views 🔗")  # Initial icon as Unicode and text
        self.clicked.connect(self.toggle_state)
        self.setFixedHeight(25)
        self.setFixedWidth(100)

    def toggle_state(self):
        """Set text and icon depending on toggle state"""

        if self.isChecked():
            self.setText("Stop sync ❌")  # Replace with your chosen broken link symbol
        else:
            self.setText("Sync views 🔗 ")
