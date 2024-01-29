import napari
import zarr

from motile_plugin import MotileWidget
from napari.utils.theme import _themes
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(filename)s:%(lineno)d] %(levelname)-8s %(message)s"
)
# logging.getLogger('napari').setLevel(logging.DEBUG)

GRAPH_LAYER = False

_themes["dark"].font_size = "18pt"


# Load Zarr datasets
zarr_directory = "/Users/malinmayorc/data/Fluo-N2DL-HeLa.zarr"
zarr_group = zarr.open_group(zarr_directory, mode='r')
image_stack = zarr_group['test/raw'][:,0,:]
labeled_mask = zarr_group['post-processed-segmentation'][:,0,:]
labeled_mask = labeled_mask[:, :, :]

# Initialize Napari viewer
viewer = napari.Viewer()

# Add image and label layers to the viewer
viewer.add_image(image_stack, name='Image Stack')
viewer.add_labels(labeled_mask, name='Labels')

# Add your custom widget
widget = MotileWidget(viewer, graph_layer=GRAPH_LAYER)
viewer.window.add_dock_widget(widget, name="Motile")

# Start the Napari GUI event loop
napari.run()
