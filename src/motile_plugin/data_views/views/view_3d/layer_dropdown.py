from PyQt5.QtCore import pyqtSignal
from qtpy.QtWidgets import QComboBox


class LayerDropdown(QComboBox):
    """QComboBox widget with functions for updating the selected layer and to update the list of options when the list of layers is modified."""

    layer_changed = pyqtSignal(str)  # Define a signal to emit the selected layer name

    def __init__(self, viewer, layer_type: tuple):
        super().__init__()
        self.viewer = viewer
        self.layer_type = layer_type
        self.viewer.layers.events.changed.connect(self._update_dropdown)
        self.viewer.layers.events.inserted.connect(self._update_dropdown)
        self.viewer.layers.events.removed.connect(self._update_dropdown)
        self.viewer.layers.selection.events.changed.connect(self._on_selection_changed)
        self.currentIndexChanged.connect(self._emit_layer_changed)
        self._update_dropdown()

    def _on_selection_changed(self) -> None:
        """Request signal emission if the user changes the layer selection."""

        if (
            len(self.viewer.layers.selection) == 1
        ):  # Only consider single layer selection
            selected_layer = self.viewer.layers.selection.active
            if isinstance(selected_layer, self.layer_type):
                self.setCurrentText(selected_layer.name)
                self._emit_layer_changed()

    def _update_dropdown(self) -> None:
        """Update the list of options in the dropdown menu whenever the list of layers is changed"""

        selected_layer = self.currentText()
        self.clear()
        layers = [
            layer
            for layer in self.viewer.layers
            if isinstance(layer, self.layer_type) and layer.name != "label options"
        ]
        items = []
        for layer in layers:
            self.addItem(layer.name)
            items.append(layer.name)

        # In case the currently selected layer is one of the available items, set it again to the current value of the dropdown.
        if selected_layer in items:
            self.setCurrentText(selected_layer)

    def _emit_layer_changed(self):
        """Emit a signal holding the currently selected layer"""

        selected_layer = self.currentText()
        self.layer_changed.emit(selected_layer)
