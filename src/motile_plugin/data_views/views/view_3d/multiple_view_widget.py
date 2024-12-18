import napari
import numpy as np
from motile_plugin.data_views.views.layers.contour_labels import ContourLabels
from motile_plugin.data_views.views.layers.track_graph import TrackGraph
from motile_plugin.data_views.views.layers.track_labels import TrackLabels
from motile_plugin.data_views.views.layers.track_points import TrackPoints
from napari.components.layerlist import Extent
from napari.components.viewer_model import ViewerModel
from napari.layers import Labels, Layer, Points, Vectors
from napari.qt import QtViewer
from napari.utils.action_manager import action_manager
from napari.utils.events.event import WarningEmitter
from napari.utils.notifications import show_info
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QSplitter,
)
from superqt.utils import qthrottled


def copy_layer(layer: Layer, name: str = ""):
    if isinstance(layer, TrackLabels):
        res_layer = ContourLabels(
            data=layer.data,
            name=layer.name,
            colormap=layer.colormap,
            opacity=layer.opacity,
            scale=layer.scale,
        )
    elif isinstance(layer, TrackPoints):
        res_layer = Points(
            data=layer.data,
            name=layer.name,
            symbol=layer.symbol,
            face_color=layer.face_color,
            size=layer.size,
            properties=layer.properties,
            border_color=layer.border_color,
            scale=layer.scale,
            blending="translucent_no_depth",
        )
    else:
        res_layer = Layer.create(*layer.as_layer_data_tuple())

    res_layer.metadata["viewer_name"] = name
    return res_layer


def get_property_names(layer: Layer):
    klass = layer.__class__
    res = []
    for event_name, event_emitter in layer.events.emitters.items():
        if isinstance(event_emitter, WarningEmitter):
            continue
        if event_name in ("thumbnail", "name"):
            continue
        if (
            isinstance(getattr(klass, event_name, None), property)
            and getattr(klass, event_name).fset is not None
        ):
            res.append(event_name)
    return res


def center_cross_on_mouse(
    viewer_model: napari.components.viewer_model.ViewerModel,
):
    """move the cross to the mouse position"""

    if not getattr(viewer_model, "mouse_over_canvas", True):
        # There is no way for napari 0.4.15 to check if mouse is over sending canvas.
        show_info("Mouse is not over the canvas. You may need to click on the canvas.")
        return

    viewer_model.dims.current_step = tuple(
        np.round(
            [
                max(min_, min(p, max_)) / step
                for p, (min_, max_, step) in zip(
                    viewer_model.cursor.position, viewer_model.dims.range, strict=False
                )
            ]
        ).astype(int)
    )


action_manager.register_action(
    name="napari:move_point",
    command=center_cross_on_mouse,
    description="Move dims point to mouse position",
    keymapprovider=ViewerModel,
)

action_manager.bind_shortcut("napari:move_point", "T")


class own_partial:
    """
    Workaround for deepcopy not copying partial functions
    (Qt widgets are not serializable)
    """

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *args, **kwargs):
        return self.func(*(self.args + args), **{**self.kwargs, **kwargs})


class QtViewerWrap(QtViewer):
    def __init__(self, main_viewer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main_viewer = main_viewer

    def _qt_open(
        self,
        filenames: list,
        stack: bool,
        plugin: str = None,
        layer_type: str = None,
        **kwargs,
    ):
        """for drag and drop open files"""
        self.main_viewer.window._qt_viewer._qt_open(
            filenames, stack, plugin, layer_type, **kwargs
        )


class CrossWidget(QCheckBox):
    """
    Widget to control the cross layer. because of the performance reason
    the cross update is throttled
    """

    def __init__(self, viewer: napari.Viewer):
        super().__init__("Add cross layer")
        self.viewer = viewer
        self.setChecked(False)
        self.stateChanged.connect(self._update_cross_visibility)
        self.layer = None
        self.viewer.dims.events.order.connect(self.update_cross)
        self.viewer.dims.events.ndim.connect(self._update_ndim)
        self.viewer.dims.events.current_step.connect(self.update_cross)
        self._extent = None

        self._update_extent()
        self.viewer.dims.events.connect(self._update_extent)

    @qthrottled(leading=False)
    def _update_extent(self):
        """
        Calculate the extent of the data.

        Ignores the cross layer itself in calculating the extent.
        """

        extent_list = [
            layer.extent for layer in self.viewer.layers if layer is not self.layer
        ]
        self._extent = Extent(
            data=None,
            world=self.viewer.layers._get_extent_world(extent_list),
            step=self.viewer.layers._get_step_size(extent_list),
        )
        self.update_cross()

    def _update_ndim(self, event):
        if self.layer in self.viewer.layers:
            self.viewer.layers.remove(self.layer)
        self.layer = Vectors(name=".cross", ndim=event.value)
        self.layer.edge_width = 1
        self.update_cross()

    def _update_cross_visibility(self, state):
        if state:
            self.viewer.layers.append(self.layer)
        else:
            self.viewer.layers.remove(self.layer)
        self.update_cross()

    def update_cross(self):
        if self.layer not in self.viewer.layers:
            self.setChecked(False)
            return

        point = self.viewer.dims.current_step
        vec = []
        for i, (lower, upper) in enumerate(self._extent.world.T):
            if (upper - lower) / self._extent.step[i] == 1:
                continue
            point1 = list(point)
            point1[i] = (lower + self._extent.step[i] / 2) / self._extent.step[i]
            point2 = [0 for _ in point]
            point2[i] = (upper - lower) / self._extent.step[i]
            vec.append((point1, point2))
        if np.any(self.layer.scale != self._extent.step):
            self.layer.scale = self._extent.step
        self.layer.data = vec


class MultipleViewerWidget(QSplitter):
    """The main widget of the example."""

    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.viewer = viewer
        self.viewer_model1 = ViewerModel(title="model1")
        self.viewer_model2 = ViewerModel(title="model2")
        self._block = False
        self.qt_viewer1 = QtViewerWrap(viewer, self.viewer_model1)
        self.qt_viewer2 = QtViewerWrap(viewer, self.viewer_model2)
        viewer_splitter = QSplitter()
        viewer_splitter.setOrientation(Qt.Vertical)
        viewer_splitter.addWidget(self.qt_viewer1)
        viewer_splitter.addWidget(self.qt_viewer2)
        viewer_splitter.setContentsMargins(0, 0, 0, 0)

        self.addWidget(viewer_splitter)

        self.viewer.layers.events.inserted.connect(self._layer_added)
        self.viewer.layers.events.removed.connect(self._layer_removed)
        self.viewer.layers.events.moved.connect(self._layer_moved)
        self.viewer.layers.selection.events.active.connect(
            self._layer_selection_changed
        )
        self.viewer.dims.events.current_step.connect(self._point_update)
        self.viewer_model1.dims.events.current_step.connect(self._point_update)
        self.viewer_model2.dims.events.current_step.connect(self._point_update)
        self.viewer.dims.events.order.connect(self._order_update)
        self.viewer.events.reset_view.connect(self._reset_view)
        self.viewer_model1.events.status.connect(self._status_update)
        self.viewer_model2.events.status.connect(self._status_update)

        # add any existing layers to viewer
        for layer in self.viewer.layers:
            self.viewer_model1.layers.insert(0, copy_layer(layer, "model1"))
            self.viewer_model2.layers.insert(0, copy_layer(layer, "model2"))
            for name in get_property_names(layer):
                getattr(layer.events, name).connect(
                    own_partial(self._property_sync, name)
                )

            if isinstance(layer, Labels):
                layer.events.set_data.connect(self._set_data_refresh)
                self.viewer_model1.layers[layer.name].events.set_data.connect(
                    self._set_data_refresh
                )
                self.viewer_model2.layers[layer.name].events.set_data.connect(
                    self._set_data_refresh
                )

            # connect events
            if layer.name != ".cross":
                self.viewer_model1.layers[layer.name].events.data.connect(
                    self._sync_data
                )

                self.viewer_model2.layers[layer.name].events.data.connect(
                    self._sync_data
                )

            layer.events.name.connect(self._sync_name)

            self._order_update()

    def _status_update(self, event):
        self.viewer.status = event.value

    def _reset_view(self):
        self.viewer_model1.reset_view()
        self.viewer_model2.reset_view()

    def _reset_layers(self):
        self.viewer_model1.layers.clear()
        self.viewer_model2.layers.clear()

    def _layer_selection_changed(self, event):
        """
        update of current active layer
        """
        if self._block:
            return

        if event.value is None:
            self.viewer_model1.layers.selection.active = None
            self.viewer_model2.layers.selection.active = None
            return

        if event.value.name in self.viewer_model1.layers:
            self.viewer_model1.layers.selection.active = self.viewer_model1.layers[
                event.value.name
            ]
        if event.value.name in self.viewer_model2.layers:
            self.viewer_model2.layers.selection.active = self.viewer_model2.layers[
                event.value.name
            ]

    def _point_update(self, event):
        try:
            for model in [self.viewer, self.viewer_model1, self.viewer_model2]:
                if model.dims is event.source:
                    continue
                model.dims.current_step = event.value
        except IndexError:
            "Layer was already removed! This error likely occurs because two actions are called at the same time."

    def _order_update(self):
        order = list(self.viewer.dims.order)
        if len(order) <= 2:
            self.viewer_model1.dims.order = order
            self.viewer_model2.dims.order = order
            return

        order[-3:] = order[-2], order[-3], order[-1]
        self.viewer_model1.dims.order = order
        order = list(self.viewer.dims.order)
        order[-3:] = order[-1], order[-2], order[-3]
        self.viewer_model2.dims.order = order

    def _layer_added(self, event):
        """add layer to additional viewers and connect all required events"""

        if (
            event.value.name not in self.viewer_model1.layers
            and event.value.name not in self.viewer_model2.layers
        ):
            # do not include TrackGraphs in the orthogonal views
            if isinstance(event.value, TrackGraph):
                return

            self.viewer_model1.layers.insert(
                event.index, copy_layer(event.value, "model1")
            )
            self.viewer_model2.layers.insert(
                event.index, copy_layer(event.value, "model2")
            )
            for name in get_property_names(event.value):
                getattr(event.value.events, name).connect(
                    own_partial(self._property_sync, name)
                )

            if isinstance(event.value, Labels):
                event.value.events.set_data.connect(self._set_data_refresh)
                self.viewer_model1.layers[event.value.name].events.set_data.connect(
                    self._set_data_refresh
                )
                self.viewer_model2.layers[event.value.name].events.set_data.connect(
                    self._set_data_refresh
                )

            if isinstance(event.value, TrackPoints):
                event.value.events.border_color.connect(self._sync_shown_points)

            # connect data and paint events
            if event.value.name != ".cross":
                self.viewer_model1.layers[event.value.name].events.data.connect(
                    self._sync_data
                )
                if isinstance(self.viewer_model1.layers[event.value.name], Labels):
                    self.viewer_model1.layers[event.value.name].events.paint.connect(
                        self._sync_paint
                    )
                    self.viewer_model1.layers[
                        event.value.name
                    ].mouse_drag_callbacks.append(self._sync_click)

                if isinstance(self.viewer_model1.layers[event.value.name], Points):
                    self.viewer_model1.layers[
                        event.value.name
                    ].mouse_drag_callbacks.append(self._sync_point_click)

                self.viewer_model2.layers[event.value.name].events.data.connect(
                    self._sync_data
                )

                if isinstance(self.viewer_model2.layers[event.value.name], Points):
                    self.viewer_model2.layers[
                        event.value.name
                    ].mouse_drag_callbacks.append(self._sync_point_click)

                if isinstance(self.viewer_model2.layers[event.value.name], Labels):
                    self.viewer_model2.layers[event.value.name].events.paint.connect(
                        self._sync_paint
                    )
                self.viewer_model2.layers[event.value.name].mouse_drag_callbacks.append(
                    self._sync_click
                )

            event.value.events.name.connect(self._sync_name)

            self._order_update()

    def _sync_point_click(self, layer, event):
        """Retrieve the label that was clicked on and forward it to the TrackLabels instance if present"""

        name = layer.name
        if (
            event.type == "mouse_press"
            and name in self.viewer.layers
            and isinstance(self.viewer.layers[name], TrackPoints)
        ):
            point_index = layer.get_value(
                event.position,
                view_direction=event.view_direction,
                dims_displayed=event.dims_displayed,
                world=True,
            )
            if point_index is not None:
                self.viewer.layers[name].process_point_click(point_index, event)

    def _sync_click(self, layer, event):
        """Retrieve the label that was clicked on and forward it to the TrackLabels instance if present"""

        name = layer.name
        if (
            event.type == "mouse_press"
            and layer.mode == "pan_zoom"
            and name in self.viewer.layers
            and isinstance(self.viewer.layers[name], TrackLabels)
        ):
            label = layer.get_value(
                event.position,
                view_direction=event.view_direction,
                dims_displayed=event.dims_displayed,
                world=True,
            )

            # Process the click event on the TrackLabels instance
            self.viewer.layers[name].process_click(event, label)

    def _sync_paint(self, event):
        """Forward the paint event to the TrackLabels, if present"""

        if event.source.name in self.viewer.layers and isinstance(
            self.viewer.layers[event.source.name], TrackLabels
        ):
            self.viewer.layers[event.source.name]._on_paint(event)

    def _sync_name(self, event):
        """sync name of layers"""

        try:
            index = self.viewer.layers.index(event.source)
            self.viewer_model1.layers[index].name = event.source.name
            self.viewer_model2.layers[index].name = event.source.name
        except IndexError:
            return

    def _sync_data(self, event):
        """sync data modification from additional viewers"""

        if self._block:
            return
        for model in [self.viewer, self.viewer_model1, self.viewer_model2]:
            if event.source.name in model.layers:
                layer = model.layers[event.source.name]
                if layer is event.source:
                    continue
                try:
                    self._block = True
                    layer.data = event.source.data
                finally:
                    self._block = False

    def _sync_shown_points(self, event):
        """Sync the visible points between TrackPoints layer and orthogonal views"""

        for model in [self.viewer_model1, self.viewer_model2]:
            if event.source.name in model.layers:
                layer = model.layers[event.source.name]
                if layer is event.source:
                    continue
                try:
                    self._block = True
                    layer.shown = event.source.shown
                finally:
                    self._block = False

    def _set_data_refresh(self, event):
        """
        synchronize data refresh between layers
        """
        if self._block:
            return
        for model in [self.viewer, self.viewer_model1, self.viewer_model2]:
            if event.source.name in model.layers:
                layer = model.layers[event.source.name]
                if layer is event.source:
                    continue
                try:
                    self._block = True
                    if isinstance(layer, ContourLabels):
                        layer.group_labels = event.source.group_labels
                    layer.refresh()
                finally:
                    self._block = False

    def _layer_removed(self, event):
        """remove layer in all viewers"""

        layer_name = event.value.name
        if layer_name in self.viewer_model1.layers:
            self.viewer_model1.layers.pop(layer_name)
        if layer_name in self.viewer_model2.layers:
            self.viewer_model2.layers.pop(layer_name)

    def _layer_moved(self, event):
        """update order of layers"""

        dest_index = (
            event.new_index if event.new_index < event.index else event.new_index + 1
        )
        self.viewer_model1.layers.move(event.index, dest_index)
        self.viewer_model2.layers.move(event.index, dest_index)

    def _property_sync(self, name, event):
        """Sync layers properties (except the name)"""

        if event.source.name not in self.viewer.layers:
            return
        try:
            self._block = True
            if event.source.name in self.viewer_model1.layers:
                setattr(
                    self.viewer_model1.layers[event.source.name],
                    name,
                    getattr(event.source, name),
                )
            if event.source.name in self.viewer_model2.layers:
                setattr(
                    self.viewer_model2.layers[event.source.name],
                    name,
                    getattr(event.source, name),
                )
        finally:
            self._block = False
