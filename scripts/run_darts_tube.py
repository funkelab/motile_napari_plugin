import napari
import zarr
import argparse
import logging
from pathlib import Path
import sys
from darts_utils.data import (
    RawDataZarr,
    SegmentationZarr,
    add_data_args,
    add_segmentation_args,
)
import yaml
from motile_plugin import MotileWidget
from napari.utils.theme import _themes
from funlib.geometry.roi import Roi

_themes["dark"].font_size = "18pt"
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)-8s %(message)s"
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    args = parser.parse_args()

    with open(args.config) as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            print(exc)

    storage_config = config["storage"]
    dataset_config = config["dataset"]    

    base_path = storage_config["data_base_path"]
    seg_path = storage_config["seg_base_path"]
    experiments_path = Path(storage_config["exp_base_path"])

    ds_name = dataset_config["dataset"]
    result_names = dataset_config["result_names"]
    roi = Roi(dataset_config["roi_offset"], dataset_config["roi_shape"])
    
    raw_zarr = RawDataZarr(base_path, ds_name, mode="r", store_type="flat")
    if not "fov" in dataset_config:
        fovs = raw_zarr.get_fovs()
        if not fovs:
            print(f"no fovs for dataset {ds_name}, exiting")
            sys.exit()
        fov = raw_zarr.get_fovs()[0]
    else:
        fov = dataset_config["fov"]

    if not "channels" in dataset_config:
        channels = raw_zarr.get_channels(fov)
    else:
        channels = dataset_config["channels"]
    seg_zarr = SegmentationZarr(
                seg_path, ds_name, None, mode="r"
            )
    
    print("Starting napari viewer")
    # Initialize Napari viewer
    viewer = napari.Viewer()
    for channel in channels:
        print(f"Adding images for channel {channel}")
        image_stack = raw_zarr.get_data(fov, channel)
        image_stack = image_stack[raw_zarr.roi_to_slices(roi)]
        viewer.add_image(image_stack[:, 0], name=f"{channel}_raw")

        fluorescent_prefixes = [
            "mCherry",
            "RFP",
            "YFP",
            "GFP",
            "CFP",
        ]
        if any(prefix in channel for prefix in fluorescent_prefixes):
            for result in result_names:
                seg_zarr.set_result_name(result)
                labeled_mask = seg_zarr.get_data(fov, channel)
                labeled_mask = labeled_mask[seg_zarr.roi_to_slices(roi)]
                viewer.add_labels(labeled_mask[:,0], name=f"{channel}_{result}")
            
    
    print("Done adding images")
    # Add your custom widget

    ds_exp_path = experiments_path  / ds_name
    ds_exp_path.mkdir(exist_ok=True)
    widget = MotileWidget(viewer, storage_path=ds_exp_path)
    viewer.window.add_dock_widget(widget)

    # Start the Napari GUI event loop
    napari.run()
