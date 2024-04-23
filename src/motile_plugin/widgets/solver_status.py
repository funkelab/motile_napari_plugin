from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel
)
import pyqtgraph as pg

class SolverStatus(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        self.label = QLabel("Solver is running")
        self.gap_plot = self._plot_widget()
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.gap_plot)
        self.setLayout(main_layout)
        self.gaps = []

    def _plot_widget(self) -> pg.PlotWidget:
        gap_plot = pg.PlotWidget()
        gap_plot.setBackground((37, 41, 49))
        styles = {"color": "white",}
        gap_plot.setLabel("left", "Gap", **styles)
        gap_plot.setLabel("bottom", "Solver round", **styles)
        gap_plot.getPlotItem().setLogMode(x=False, y=True)
        return gap_plot

    def update(self, event_data):
        event_type = event_data["event_type"]
        backend = event_data["backend"]
        if event_type in ["PRESOLVE", "PRESOLVEROUND"]:
            print(f"presolving")
            self.label.setText("Solver is in presolving.")
        elif event_type in ["MIPSOL", "BESTSOLFOUND"]:
            self.label.setText("Solver is solving.")
            gap = event_data["gap"]
            print(f"{gap=}")
            self.gaps.append(event_data["gap"])
            gaps = self.gaps
            if backend == "gurobi":
                # don't plot first gap, because it is weird
                gaps = gaps[1:]
            self.gap_plot.getPlotItem().plot(range(len(gaps)), gaps)


    def reset(self):
        self.gaps = []
        self.gap_plot.getPlotItem().clear()