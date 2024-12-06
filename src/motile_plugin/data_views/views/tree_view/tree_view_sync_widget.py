from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SyncWidget(QWidget):
    """Widget to switch between viewing all nodes versus nodes of one or more lineages in the tree widget"""

    def __init__(self):
        super().__init__()

        sync_box = QGroupBox("Sync/Desync views")
        sync_layout = QHBoxLayout()
        self.sync_button = SyncButton()
        sync_layout.addWidget(self.sync_button)
        sync_box.setLayout(sync_layout)
        layout = QVBoxLayout()
        layout.addWidget(sync_box)
        sync_box.setMaximumWidth(150)
        sync_box.setMaximumHeight(60)

        self.setLayout(layout)


class SyncButton(QPushButton):
    def __init__(self):
        super().__init__()

        self.setCheckable(True)
        self.setText("🔗")  # Initial icon as Unicode and text
        self.clicked.connect(self.toggle_state)
        self.setFixedHeight(25)

    def toggle_state(self):
        """Set text and icon depending on toggle state"""

        if self.isChecked():
            self.setText("❌")  # Replace with your chosen broken link symbol
        else:
            self.setText("🔗 ")
