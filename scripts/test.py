import napari

from motile_plugin import ExampleQWidget

viewer = napari.Viewer()

widget = ExampleQWidget(viewer)
viewer.window.add_dock_widget(widget)
napari.run()