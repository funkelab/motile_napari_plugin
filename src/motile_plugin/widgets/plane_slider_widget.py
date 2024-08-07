from functools import partial
from typing import Tuple

import napari.layers
import numpy as np
from qtpy import QtCore
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledSlider

from motile_plugin.widgets.tracking_view_controller import (
    TrackingViewController,
)

class PlaneSliderWidget(QWidget):
    """Widget for extended 3D visualization purposes only,
    constructs additional layers and allows switching between plane and volume mode.
    """

    def __init__(
        self,
        viewer: napari.Viewer,
    ):
        super().__init__()

        self.viewer = viewer
        self.view_controller = TrackingViewController.get_instance(viewer)
        self.view_controller.tracking_layers_updated.connect(self._update)

        self.plane_colormap = self.view_controller.colormap
       
        self.intensity_images = [
            layer
            for layer in self.viewer.layers
            if isinstance(layer, napari.layers.Image)
        ]

        self.z_plane_layers = []
        self.y_plane_layers = []
        self.x_plane_layers = []
        self.volume_layer = None

        self.viewer.layers.selection.clear()

        self.viewer.dims.events.ndisplay.connect(self.on_ndisplay_changed)
        view_mode_widget_layout = QVBoxLayout()

        # Add buttons to switch between plane and volume mode
        volume_view_box = QGroupBox("3D view")
        button_layout = QVBoxLayout()

        plane_volume_layout = QHBoxLayout()
        self.plane_btn = QPushButton("Plane")
        self.plane_btn.setEnabled(False)
        self.plane_btn.clicked.connect(self._set_plane_mode)
        self.volume_btn = QPushButton("Volume")
        self.volume_btn.setEnabled(True)
        self.volume_btn.clicked.connect(self._set_volume_mode)
        plane_volume_layout.addWidget(self.plane_btn)
        plane_volume_layout.addWidget(self.volume_btn)
        button_layout.addLayout(plane_volume_layout)

        # Add plane sliders for viewing in 3D
        z_layout = QVBoxLayout()

        self.z_plane_btn = QCheckBox()
        self.z_plane_btn.setEnabled(False)
        self.y_plane_btn = QCheckBox()
        self.y_plane_btn.setEnabled(False)
        self.x_plane_btn = QCheckBox()
        self.x_plane_btn.setEnabled(False)

        self.z_plane_btn.stateChanged.connect(
            partial(self._toggle_slider, "z")
        )
        self.y_plane_btn.stateChanged.connect(
            partial(self._toggle_slider, "y")
        )
        self.x_plane_btn.stateChanged.connect(
            partial(self._toggle_slider, "x")
        )

        z_label = QLabel("z")
        self.z_plane_slider = QLabeledSlider(QtCore.Qt.Vertical)
        self.z_plane_slider.setSingleStep(1)
        self.z_plane_slider.setTickInterval(1)
        self.z_plane_slider.setValue(0)
        self.z_plane_slider.setEnabled(False)
        self.z_plane_slider.valueChanged.connect(lambda: self._set_plane("z"))
        self.z_plane_slider.setMaximumWidth(20)

        z_layout.addWidget(z_label)
        z_layout.addWidget(self.z_plane_btn)
        z_layout.addWidget(self.z_plane_slider)

        y_layout = QVBoxLayout()
        y_label = QLabel("y")
        self.y_plane_slider = QLabeledSlider(QtCore.Qt.Vertical)
        self.y_plane_slider.setSingleStep(1)
        self.y_plane_slider.setTickInterval(1)
        self.y_plane_slider.setValue(0)
        self.y_plane_slider.setEnabled(False)
        self.y_plane_slider.valueChanged.connect(lambda: self._set_plane("y"))
        self.y_plane_slider.setMaximumWidth(20)

        y_layout.addWidget(y_label)
        y_layout.addWidget(self.y_plane_btn)
        y_layout.addWidget(self.y_plane_slider)

        x_layout = QVBoxLayout()
        x_label = QLabel("x")
        self.x_plane_slider = QLabeledSlider(QtCore.Qt.Vertical)
        self.x_plane_slider.setSingleStep(1)
        self.x_plane_slider.setTickInterval(1)
        self.x_plane_slider.setValue(0)
        self.x_plane_slider.setEnabled(False)
        self.x_plane_slider.valueChanged.connect(lambda: self._set_plane("x"))
        self.x_plane_slider.setMaximumWidth(20)

        x_layout.addWidget(x_label)
        x_layout.addWidget(self.x_plane_btn)
        x_layout.addWidget(self.x_plane_slider)

        slider_layout = QHBoxLayout()
        slider_layout.addLayout(z_layout)
        slider_layout.addLayout(y_layout)
        slider_layout.addLayout(x_layout)

        view_mode_widget_layout.addLayout(button_layout)
        view_mode_widget_layout.addLayout(slider_layout)
        volume_view_box.setLayout(view_mode_widget_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(volume_view_box)

        self.setLayout(main_layout)
        self.on_ndisplay_changed()

    def _update(self,):
        """Update sliders and reinitialize viewing layers"""

        self.plane_colormap = self.view_controller.colormap

        self.z_plane_slider.setMaximum(int(
            self.viewer.dims.range[-3].stop)
        )
        self.y_plane_slider.setMaximum(int(
            self.viewer.dims.range[-2].stop)
        )
        self.x_plane_slider.setMaximum(int(
            self.viewer.dims.range[-1].stop)
        )

        self.z_plane_layers = []
        self.y_plane_layers = []
        self.x_plane_layers = []
        self.volume_layer = None
               
        self.intensity_images = [
            layer
            for layer in self.viewer.layers
            if isinstance(layer, napari.layers.Image)
        ]

    def _set_plane_mode(self) -> None:
        """Set the mode to plane, enable slider and change depiction to 'plane' for Image and Labels layers"""

        self.plane_btn.setEnabled(False)
        self.volume_btn.setEnabled(True)
        self.z_plane_btn.setEnabled(True)
        self.y_plane_btn.setEnabled(True)
        self.x_plane_btn.setEnabled(True)
        if self.view_controller.tracking_layers.seg_layer is not None: 
            self.view_controller.tracking_layers.seg_layer.display_mode = "plane"
            self.view_controller.tracking_layers.seg_layer.update_label_colormap()

        if self.z_plane_btn.isChecked():
            self.z_plane_slider.setEnabled(True)
            for layer in self.z_plane_layers:
                self.viewer.layers.append(layer)
        if self.y_plane_btn.isChecked():
            self.y_plane_slider.setEnabled(True)
            for layer in self.y_plane_layers:
                self.viewer.layers.append(layer)
        if self.x_plane_btn.isChecked():
            self.x_plane_slider.setEnabled(True)
            for layer in self.x_plane_layers:
                self.viewer.layers.append(layer)

        if self.volume_layer is not None: 
            if self.volume_layer in self.viewer.layers:
                self.viewer.layers.remove(self.volume_layer)

        for layer in self.viewer.layers:
            if isinstance(layer, napari.layers.Image):
                index = self.viewer.layers.index(layer)
                self.viewer.layers.move(
                    index, 0
                )  # move image layers to the bottom
        self.viewer.layers.selection.clear()
        self.viewer.layers.selection.add(self.view_controller.tracking_layers.points_layer)

    def _set_volume_mode(self) -> None:
        """Set the mode to volume, disable slider and change depiction to 'volume' for Image and Labels layers"""

        self.plane_btn.setEnabled(True)
        self.volume_btn.setEnabled(False)
        self.z_plane_btn.setEnabled(False)
        self.y_plane_btn.setEnabled(False)
        self.x_plane_btn.setEnabled(False)
        self.z_plane_slider.setEnabled(False)
        self.y_plane_slider.setEnabled(False)
        self.x_plane_slider.setEnabled(False)

        if self.z_plane_btn.isChecked():
            self._deactivate_slider("z")
        if self.y_plane_btn.isChecked():
            self._deactivate_slider("y")
        if self.x_plane_btn.isChecked():
            self._deactivate_slider("x")

        # add a new volume labels layer that is noneditable but displays all labels in the background 
        if self.view_controller.tracking_layers.seg_layer is not None: 
            if self.volume_layer is None: 
                self.volume_layer = self.viewer.add_labels(self.view_controller.tracking_layers.seg_layer.data, name = 'volume view (no edits)', opacity = 0.4, blending = 'translucent_no_depth', scale=self.view_controller.tracking_layers.seg_layer.scale)
                self.volume_layer.mouse_pan = False
                self.volume_layer.mouse_zoom = False
            else: 
                self.viewer.layers.append(self.volume_layer)

        # make the labels the selected layer and update colormaps
        self.viewer.layers.selection.clear()
        if self.view_controller.tracking_layers.seg_layer is not None:
            self.viewer.layers.selection.add(self.view_controller.tracking_layers.seg_layer)
            self.view_controller.tracking_layers.seg_layer.display_mode = "volume"
            self.view_controller.tracking_layers.seg_layer.update_label_colormap()
        self.view_controller.tracking_layers.points_layer.update_point_outline(plane_nodes = 'all')
        self.view_controller.tracking_layers.tracks_layer.update_track_visibility(plane_nodes = 'all')

    def on_ndisplay_changed(self) -> None:
        """Update the buttons depending on the display mode of the viewer. Buttons and slider should only be active in 3D mode"""

        if self.viewer.dims.ndisplay == 2:
            self.plane_btn.setEnabled(False)
            self.volume_btn.setEnabled(False)
            self.z_plane_btn.setEnabled(False)
            self.y_plane_btn.setEnabled(False)
            self.x_plane_btn.setEnabled(False)
            self.z_plane_slider.setEnabled(False)
            self.y_plane_slider.setEnabled(False)
            self.x_plane_slider.setEnabled(False)

            if self.z_plane_btn.isChecked():
                self._deactivate_slider("z")
            if self.y_plane_btn.isChecked():
                self._deactivate_slider("y")
            if self.x_plane_btn.isChecked():
                self._deactivate_slider("x")
            
            if self.volume_layer in self.viewer.layers:
                self.viewer.layers.remove(self.volume_layer)

            # show all the points and tracks in volume mode
            if self.view_controller.tracking_layers.points_layer is not None: 
                self.view_controller.tracking_layers.points_layer.update_point_outline(plane_nodes = 'all')
            if self.view_controller.tracking_layers.tracks_layer is not None:
                self.view_controller.tracking_layers.tracks_layer.track_colors[:, 3] = 1
                self.view_controller.tracking_layers.tracks_layer.display_graph = True
                self.view_controller.tracking_layers.tracks_layer.events.rebuild_tracks()  # fire the event to update the colors
            if self.view_controller.tracking_layers.seg_layer is not None: 
                self.view_controller.tracking_layers.seg_layer.display_mode = "slice"
                self.view_controller.tracking_layers.seg_layer.update_label_colormap()
        else:
            self._set_volume_mode()

    def _set_plane_value(self, pos: Tuple) -> None:
        """Set the plane slider to specific value"""

        self.z_plane_slider.setValue(pos[0])
        self.y_plane_slider.setValue(pos[1])
        self.x_plane_slider.setValue(pos[2])

        if self.z_plane_btn.isChecked():
            self._set_plane(axis="z")
        elif self.y_plane_btn.isChecked():
            self._set_plane(axis="y")
        elif self.x_plane_btn.isChecked():
            self._set_plane(axis="x")

    def _toggle_slider(self, axis: str, state: int) -> None:
        """Call to activate or deactivate the sliders"""

        if state == 2:
            self._activate_slider(axis)
        else:
            self._deactivate_slider(axis)

    def _deactivate_slider(self, axis: str) -> None:
        """Deactivate the slider for the given axis and remove all associated layers"""

        if axis == "z":
            for layer in self.z_plane_layers:
                if layer in self.viewer.layers:
                    self.viewer.layers.remove(layer)
            self.z_plane_slider.setEnabled(False)

        if axis == "y":
            for layer in self.y_plane_layers:
                if layer in self.viewer.layers:
                    self.viewer.layers.remove(layer)
            self.y_plane_slider.setEnabled(False)

        if axis == "x":
            for layer in self.x_plane_layers:
                if layer in self.viewer.layers:
                    self.viewer.layers.remove(layer)
            self.x_plane_slider.setEnabled(False)

    def _activate_slider(self, axis: str) -> None:
        """Activates or deactivates a plane"""

        layers = [
            layer
            for layer in self.viewer.layers
            if layer in self.intensity_images
            or layer == self.view_controller.tracking_layers.seg_layer
        ]

        for layer in layers:
            if axis == "z":

                if isinstance(layer, napari.layers.Image):
                    z_layer = self.viewer.add_image(
                        layer.data, name="z plane of " + layer.name, scale=layer.scale
                    )
                else:
                    z_layer = self.viewer.add_labels(
                        layer.data,
                        name="z plane of " + layer.name,
                        colormap=self.plane_colormap,
                        opacity=0.4,
                        scale=layer.scale
                    )
                    z_layer.rendering = "translucent"
                z_layer.depiction = "plane"
                z_layer.plane.normal = (1, 0, 0)
                z_layer.mouse_pan = False
                z_layer.mouse_zoom = False

                self.z_plane_slider.setEnabled(True)
                self._set_plane(axis="z")

                self.z_plane_layers.append(z_layer)

            if axis == "y":

                if isinstance(layer, napari.layers.Image):
                    y_layer = self.viewer.add_image(
                        layer.data, name="y plane of " + layer.name, scale=layer.scale,
                    )
                else:
                    y_layer = self.viewer.add_labels(
                        layer.data,
                        name="y plane of " + layer.name,
                        colormap=self.plane_colormap,
                        opacity=0.4,
                        scale=layer.scale
                    )
                    y_layer.rendering = "translucent"

                y_layer.depiction = "plane"
                y_layer.plane.normal = (0, 1, 0)
                y_layer.mouse_pan = False
                y_layer.mouse_zoom = False

                self.y_plane_slider.setEnabled(True)
                self._set_plane(axis="y")

                self.y_plane_layers.append(y_layer)

            if axis == "x":

                if isinstance(layer, napari.layers.Image):
                    x_layer = self.viewer.add_image(
                        layer.data, name="x plane of " + layer.name, scale=layer.scale
                    )
                else:
                    x_layer = self.viewer.add_labels(
                        layer.data,
                        name="x plane of " + layer.name,
                        colormap=self.plane_colormap,
                        opacity=0.4,
                        scale=layer.scale
                    )
                    x_layer.rendering = "translucent"
                x_layer.plane.normal = (0, 0, 1)
                x_layer.mouse_pan = False
                x_layer.mouse_zoom = False
                x_layer.depiction = "plane"

                self.x_plane_slider.setEnabled(True)
                self._set_plane(axis="x")

                self.x_plane_layers.append(x_layer)

            self.viewer.layers.selection.clear()
            self.viewer.layers.selection.add(self.view_controller.tracking_layers.points_layer)

            for layer in self.viewer.layers:
                if isinstance(layer, napari.layers.Image):
                    index = self.viewer.layers.index(layer)
                    self.viewer.layers.move(
                        index, 0
                    )  # move image layers to the bottom

    def _set_plane(self, axis: str) -> None:
        """Adjusts the plane position of Image and Labels layers. Display only points and tracks belonging to the visible labels in this plane"""

        if axis == "z":
            slider_position = self.z_plane_slider.value()

            for layer in self.z_plane_layers:
                pos = layer.plane.position
                layer.plane.position = (slider_position, pos[1], pos[2])
            labels_shown = np.unique(
                self.view_controller.tracking_layers.seg_layer.data[
                    self.viewer.dims.current_step[0], slider_position, :, :
                ]
            )

        if axis == "y":
            slider_position = self.y_plane_slider.value()
            for layer in self.y_plane_layers:
                pos = layer.plane.position
                layer.plane.position = (pos[0], slider_position, pos[2])
            labels_shown = np.unique(
                self.view_controller.tracking_layers.seg_layer.data[
                    self.viewer.dims.current_step[0], :, slider_position, :
                ]
            )

        if axis == "x":
            slider_position = self.x_plane_slider.value()
            for layer in self.x_plane_layers:
                pos = layer.plane.position
                layer.plane.position = (pos[0], pos[1], slider_position)
            labels_shown = np.unique(
                self.view_controller.tracking_layers.seg_layer.data[
                    self.viewer.dims.current_step[0], :, :, slider_position
                ]
            )

        # specify which points and tracks to show and which not to show
        self.view_controller.tracking_layers.points_layer.update_point_outline(plane_nodes = labels_shown)
        self.view_controller.tracking_layers.tracks_layer.update_track_visibility(plane_nodes = labels_shown)
