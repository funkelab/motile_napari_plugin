import logging
from pathlib import Path

import napari
import zarr
from appdirs import AppDirs
from motile_tracker.application_menus import MainApp
from motile_tracker.data_views import TreeWidget
from napari.utils.theme import _themes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(filename)s:%(lineno)d] %(levelname)-8s %(message)s",
)
logging.getLogger("motile_tracker").setLevel(logging.DEBUG)

_themes["dark"].font_size = "18pt"


# Load Zarr datasets

ds_name = "Fluo-N2DL-HeLa"
appdir = AppDirs("motile-tracker")
data_dir = Path(appdir.user_data_dir)
zarr_directory = data_dir / f"{ds_name}.zarr"
zarr_group = zarr.open_group(zarr_directory, mode="r")

# Initialize Napari viewer
viewer = napari.Viewer()

# Add image and label layers to the viewer
viewer.add_image(zarr_group["01"][:], name="01 Raw")
viewer.add_labels(zarr_group["01_ST"][:], name="01 ST")

# Add your custom widget
widget = MainApp(viewer)
viewer.window.add_dock_widget(widget, name="Motile")

# Start the Napari GUI event loop
napari.run()
