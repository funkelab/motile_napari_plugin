import napari
import zarr

from motile_plugin import MotileWidget

# Load Zarr datasets
zarr_directory = "/Volumes/funke$/lalitm/cellulus/experiments/data/science_meet/Fluo-N2DL-HeLa.zarr"
zarr_group = zarr.open_group(zarr_directory, mode='r')
image_stack = zarr_group['test/raw'][:,0,:]
labeled_mask = zarr_group['post-processed-segmentation'][:,0,:]
labeled_mask = labeled_mask[:, :, :]

# Initialize Napari viewer
viewer = napari.Viewer()

# Add image and label layers to the viewer
viewer.add_image(image_stack, name='Image Stack')
viewer.add_labels(labeled_mask, name='Labeled Mask')

# Add your custom widget
widget = MotileWidget(viewer)
viewer.window.add_dock_widget(widget)

# Start the Napari GUI event loop
napari.run()
