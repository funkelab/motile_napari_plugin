import napari
import zarr

from motile_plugin import MotileWidget
from napari.utils.theme import _themes
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(filename)s:%(lineno)d] %(levelname)-8s %(message)s"
)
# logging.getLogger('napari').setLevel(logging.DEBUG)

_themes["dark"].font_size = "18pt"


# Load Zarr datasets
zarr_directory = "../data/Fluo-N2DL-HeLa.zarr"
zarr_group = zarr.open_group(zarr_directory, mode='r')

# Initialize Napari viewer
viewer = napari.Viewer()

# Add image and label layers to the viewer
viewer.add_image(zarr_group['01'][:], name='01 Raw')
viewer.add_labels(zarr_group['01_ST'][:], name='01 ST')

# Add your custom widget
widget = MotileWidget(viewer)
viewer.window.add_dock_widget(widget, name="Motile")

# Start the Napari GUI event loop
napari.run()
