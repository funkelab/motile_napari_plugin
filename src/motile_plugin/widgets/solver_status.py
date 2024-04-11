from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel
)

class SolverStatus(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel("Solver is running"))
        self.setLayout(main_layout)
        self.presolving = False
        self.round = 0
        self.gap = None

    def update(self, event_data):
        event_type = event_data["event_type"]
        if event_type in ["PRESOLVE", "PRESOLVEROUND"]:
            self.presolving = True
        elif event_type in ["MIPSOL", "BESTSOLFOUND"]:
            self.presolving = False
            self.round += 1
            self.gap = event_data["gap"]

    def reset(self):
        self.presolving = False
        self.round = 0
        self.gap = None