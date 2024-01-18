import napari
import zarr

from motile_plugin import ExampleQWidget

# Load Zarr datasets
zarr_directory = "/Users/kharrington/git/cmalinmayor/motile-plugin/data/zarr_data.zarr"
zarr_group = zarr.open_group(zarr_directory, mode='r')
image_stack = zarr_group['stack'][:]
labeled_mask = zarr_group['labeled_stack'][:]
labeled_mask = labeled_mask[0:5, :, :]

# Initialize Napari viewer
viewer = napari.Viewer()

# Add image and label layers to the viewer
# viewer.add_image(image_stack, name='Image Stack')
viewer.add_labels(labeled_mask, name='Labeled Mask')

# Add your custom widget
widget = ExampleQWidget(viewer)
viewer.window.add_dock_widget(widget)

# Start the Napari GUI event loop
# napari.run()
