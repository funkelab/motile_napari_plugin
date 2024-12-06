import napari
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from .clipping_plane_sliders import PlaneSliderWidget
from .multiple_view_widget import CrossWidget, MultipleViewerWidget


class OrthogonalViews(QWidget):
    def __init__(
        self,
        viewer: napari.Viewer,
    ):
        super().__init__()

        self.viewer = viewer

        self.multiple_viewer_widget = MultipleViewerWidget(self.viewer)
        self.cross_widget = CrossWidget(self.viewer)

        layout = QVBoxLayout()
        layout.addWidget(self.multiple_viewer_widget)
        layout.addWidget(self.cross_widget)

        self.setLayout(layout)


class View3D(QWidget):
    """Widget to combine multiple views and cross widget together."""

    def __init__(
        self,
        viewer: napari.Viewer,
    ):
        super().__init__()

        self.viewer = viewer
        self.viewer.dims.events.ndisplay.connect(self.display_changed)
        self.viewer.dims.events.ndim.connect(self.display_changed)

        self.orth_views = OrthogonalViews(viewer)
        self.plane_widget = PlaneSliderWidget(self.viewer)
        widget_2d_layout = QVBoxLayout()
        widget_2d_layout.addWidget(QLabel("Current data is not 3D + time"))
        self.widget_2d = QWidget()
        self.widget_2d.setLayout(widget_2d_layout)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Add both widgets to the layout but hide them initially
        self.layout().addWidget(self.orth_views)
        self.layout().addWidget(self.plane_widget)
        self.layout().addWidget(self.widget_2d)

        self.orth_views.hide()
        self.plane_widget.hide()
        self.widget_2d.hide()

        # Show the correct widget initially
        self.display_changed()

    def display_changed(self, event=None):
        """Switch between OrthogonalViews and PlaneSliderWidget based on ndisplay."""
        # Hide both widgets
        self.orth_views.hide()
        self.plane_widget.hide()
        self.widget_2d.hide()

        # Show the appropriate widget based on ndisplay
        if self.viewer.dims.ndim == 4:
            if self.viewer.dims.ndisplay == 3:
                self.plane_widget.show()
            elif self.viewer.dims.ndisplay == 2:
                self.orth_views.show()
        else:
            self.widget_2d.show()
