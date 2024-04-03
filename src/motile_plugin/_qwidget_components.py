
from qtpy.QtWidgets import (
    QComboBox,
)


class LayerSelectBox(QComboBox):
    def __init__(self, layer_type, viewer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layer_type = layer_type
        self.viewer = viewer
        self.populate()
        viewer.layers.events.inserted.connect(
            lambda e: self.add(e.value))
        viewer.layers.events.removed.connect(
            lambda e: self.remove(e.value))
        viewer.layers.events.changed.connect(
            lambda e: self.update(e.removed, e.added))

    def populate(self):
        for layer in self.viewer.layers:
            print(f"Layer {layer.name} is of type {self.layer_type}: {isinstance(layer, self.layer_type)}")
            if self.layer_type is None or isinstance(layer, self.layer_type):
                self.addItem(layer.name)
        if len(self) == 0:
            self.addItem("None")

    def add(self, layer):
        if self.layer_type is None or isinstance(layer, self.layer_type):
            self.addItem(layer.name)

    def remove(self, layer):
        index = self.findText(layer.name)
        if index != -1:
            self.removeItem(index)

    def update(self, old_layer, new_layer):
        self.remove(old_layer)
        self.add(new_layer)

    def get_layer(self):
        if self.currentText() == "None":
            return None
        return self.viewer.layers[self.currentText()]







