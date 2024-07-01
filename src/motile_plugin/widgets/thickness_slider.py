from napari import Viewer
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QSlider,
    QVBoxLayout,
    QWidget,
)


class ThicknessSlider(QWidget):
    def __init__(self, viewer: Viewer):
        super().__init__()
        layout = QVBoxLayout()
        self.viewer = viewer
        self.thickness_slider = QSlider(Qt.Horizontal)
        self.thickness_slider.setMinimum(0)
        self.thickness_slider.setMaximum(50)
        self.thickness_slider.valueChanged.connect(self.on_thickness_changed)
        self.thickness_slider.setValue(10)
        layout.addWidget(self.thickness_slider)
        self.setLayout(layout)

    def on_thickness_changed(self, value):
        self.viewer.dims.margin_left = (value, 0, 0)
        print(f"Thickness changes: {self.viewer.dims.thickness}")  # noqa G004
        print(f"margin left {self.viewer.dims.margin_left}")
