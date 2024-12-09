import logging
import os
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
import tifffile
import zarr
from appdirs import AppDirs
from napari.types import LayerData
from skimage.measure import regionprops

logger = logging.getLogger(__name__)


def Mouse_Embryo_Membrane() -> list[LayerData]:
    """Loads the Mouse Embryo Membrane raw data and segmentation data from
    the appdir "user data dir". Will download it from the Zenodo DOI if it is not present already.
    Returns:
        list[LayerData]: An image layer of raw data and a segmentation labels
            layer
    """
    ds_name = "Mouse_Embryo_Membrane"
    appdir = AppDirs("motile-tracker")
    data_dir = Path(appdir.user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_name = "imaging.tif"
    label_name = "segmentation.tif"
    return read_zenodo_dataset(ds_name, raw_name, label_name, data_dir)


def Fluo_N2DL_HeLa() -> list[LayerData]:
    """Loads the Fluo-N2DL-HeLa 01 training raw data and silver truth from
    the appdir "user data dir". Will download it from the CTC and convert it to
    zarr if it is not present already.
    Returns:
        list[LayerData]: An image layer of 01 training raw data and a labels
            layer of 01 training silver truth labels
    """
    ds_name = "Fluo-N2DL-HeLa"
    appdir = AppDirs("motile-tracker")
    data_dir = Path(appdir.user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return read_ctc_dataset(ds_name, data_dir)


def Fluo_N2DL_HeLa_crop() -> list[LayerData]:
    """Loads the Fluo-N2DL-HeLa 01 training raw data and silver truth from
    the appdir "user data dir". Will download it from the CTC and convert it to
    zarr if it is not present already.
    Returns:
        list[LayerData]: An image layer of 01 training raw data and a labels
            layer of 01 training silver truth labels
    """
    ds_name = "Fluo-N2DL-HeLa"
    appdir = AppDirs("motile-tracker")
    data_dir = Path(appdir.user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return read_ctc_dataset(ds_name, data_dir, crop_region=True)


def read_zenodo_dataset(
    ds_name: str, raw_name: str, label_name: str, data_dir: Path
) -> list[LayerData]:
    """Read a zenodo dataset (assumes pre-downloaded)
    and returns a list of layer data for making napari layers

    Args:
        ds_name (str): name to give to the dataset
        raw_name (str): name of the file that points to the intensity data
        label_name (str): name of the file that points to the segmentation data
        data_dir (Path): Path to the directory containing the images

    Returns:
        list[LayerData]: An image layer of raw data and a segmentation labels
            layer
    """
    ds_zarr = data_dir / (ds_name + ".zarr")
    if not ds_zarr.exists():
        logger.info("Downloading %s", ds_name)
        download_zenodo_dataset(ds_name, raw_name, label_name, data_dir)

    raw_data = zarr.open(store=ds_zarr, path="01_membrane", dimension_separator="/")[:]
    raw_layer_data = (raw_data, {"name": "01_membrane"}, "image")
    seg_data = zarr.open(ds_zarr, path="01_labels", dimension_separator="/")[:]
    seg_layer_data = (seg_data, {"name": "01_labels"}, "labels")
    return [raw_layer_data, seg_layer_data]


def read_ctc_dataset(
    ds_name: str, data_dir: Path, crop_region=False
) -> list[LayerData]:
    """Read a CTC dataset from a zarr (assumes pre-downloaded and converted)
    and returns a list of layer data for making napari layers

    Args:
        ds_name (str): Dataset name
        data_dir (Path): Path to the directory containing the zarr

    Returns:
        list[LayerData]: An image layer of 01 training raw data and a labels
            layer of 01 training silver truth labels
    """
    ds_zarr = data_dir / (ds_name + ".zarr")
    if not ds_zarr.exists():
        logger.info("Downloading %s", ds_name)
        download_ctc_dataset(ds_name, data_dir)
    zarr_store = zarr.open(store=ds_zarr, mode="a")  # Open in append mode ('a')
    raw_data = zarr_store["01"]
    seg_data = zarr_store["01_ST"]
    min_y = 90
    min_x = 700
    max_y = 300
    max_x = 1040
    if crop_region:
        raw_data = raw_data[:, min_y:max_y, min_x:max_x]
        seg_data = seg_data[:, min_y:max_y, min_x:max_x]
    else:
        raw_data = raw_data[:]
        seg_data = seg_data[:]
    raw_layer_data = (raw_data, {"name": "01_raw"}, "image")
    seg_layer_data = (seg_data, {"name": "01_ST"}, "labels")

    # Check if 'points' dataset exists in the zarr file
    points_name = "points_crop" if crop_region else "points"
    if "points_file" not in zarr_store:
        logger.info("extracting centroids...")
        centroids_list = []
        for t in range(seg_data.shape[0]):  # Iterate over time frames
            frame_seg = seg_data[t]
            props = regionprops(frame_seg)
            centroids = np.array([prop.centroid for prop in props])
            time_stamped_centroids = np.column_stack(
                [np.full(centroids.shape[0], t), centroids]
            )
            centroids_list.append(time_stamped_centroids)
        all_centroids = np.vstack(centroids_list)

        # Save the centroids inside the zarr file under the 'points' key
        zarr_store.create_dataset(points_name, data=all_centroids, overwrite=True)
        logger.info("Centroids extracted and saved")
    else:
        # If 'points' dataset exists, load it
        logger.info("points dataset found, loading...")
        all_centroids = zarr_store[points_name][:]

    # Prepare points layer data for napari
    points_layer_data = (all_centroids, {"name": "centroids"}, "points")

    return [raw_layer_data, seg_layer_data, points_layer_data]


def download_zenodo_dataset(
    ds_name: str, raw_name: str, label_name: str, data_dir: Path
) -> None:
    """Download a sample dataset from zenodo doi and unzip it, then delete the zip. Then convert the tiffs to
    zarrs for the first training set consisting of 3D membrane intensity images and segmentation.

    Args:
        ds_name (str): Name to give to the dataset
        raw_name (str): Name of the file that contains the intensity data
        label_name (str): Name of the file that contains the label data
        data_dir (Path): The directory in which to store the data.
    """
    ds_file_raw = data_dir / raw_name
    ds_file_labels = data_dir / label_name
    ds_zarr = data_dir / (ds_name + ".zarr")
    url_raw = "https://zenodo.org/records/13903500/files/imaging.zip"
    url_labels = "https://zenodo.org/records/13903500/files/segmentation.zip"
    zip_filename_raw = data_dir / "imaging.zip"
    zip_filename_labels = data_dir / "segmentation.zip"

    if not zip_filename_raw.is_file():
        urlretrieve(url_raw, filename=zip_filename_raw)
    if not zip_filename_labels.is_file():
        urlretrieve(url_labels, filename=zip_filename_labels)

    with zipfile.ZipFile(zip_filename_raw, "r") as zip_ref:
        zip_ref.extractall(data_dir)
    with zipfile.ZipFile(zip_filename_labels, "r") as zip_ref:
        zip_ref.extractall(data_dir)

    zip_filename_raw.unlink()
    zip_filename_labels.unlink()

    convert_4d_arr_to_zarr(ds_file_raw, ds_zarr, "01_membrane")
    convert_4d_arr_to_zarr(ds_file_labels, ds_zarr, "01_labels")


def download_ctc_dataset(ds_name: str, data_dir: Path) -> None:
    """Download a dataset from the Cell Tracking Challenge
    and unzip it, then delete the zip. Then convert the tiffs to
    zarrs for the first training set images and silver truth.

    Args:
        ds_name (str): Dataset name, according to the CTC
        data_dir (Path): The directory in which to store the data.
    """
    ds_dir = data_dir / ds_name
    ds_zarr = data_dir / (ds_name + ".zarr")
    ctc_url = f"http://data.celltrackingchallenge.net/training-datasets/{ds_name}.zip"
    zip_filename = data_dir / f"{ds_name}.zip"
    if not zip_filename.is_file():
        urlretrieve(ctc_url, filename=zip_filename)
    with zipfile.ZipFile(zip_filename, "r") as zip_ref:
        zip_ref.extractall(data_dir)
    zip_filename.unlink()

    convert_to_zarr(ds_dir / "01", ds_zarr, "01")
    convert_to_zarr(ds_dir / "01_ST" / "SEG", ds_zarr, "01_ST", relabel=True)
    shutil.rmtree(ds_dir)


def convert_4d_arr_to_zarr(
    tiff_file: str, zarr_path: str, zarr_group: str, relabel=False
):
    """Convert 4D tiff file image data to zarr. Also deletes the tiffs!
    Args:
        tiff_file (str): string representing path to tif file to be converted
        zarr_path (str): path to the zarr file to write the output to
        zarr_group (str): group within the zarr store to write the data to
        relabel (bool): if true, relabels the segmentations to be unique over time
    """
    img = tifffile.imread(tiff_file)
    data_shape = img.shape
    data_dtype = img.dtype

    # prepare zarr
    if not os.path.exists(zarr_path):
        os.mkdir(zarr_path)
    store = zarr.NestedDirectoryStore(zarr_path)
    zarr_array = zarr.open(
        store=store,
        mode="w",
        path=zarr_group,
        shape=data_shape,
        dtype=data_dtype,
    )
    # save the time points to the zarr file
    max_label = 0
    for t in range(img.shape[0]):
        frame = img[t]
        if relabel:
            frame[frame != 0] += max_label
            max_label = int(np.max(frame))
        zarr_array[t] = frame
    os.remove(tiff_file)


def convert_to_zarr(tiff_path: Path, zarr_path: Path, zarr_group: str, relabel=False):
    """Convert tiff file image data to zarr. Also deletes the tiffs!
    Args:
        tif_path (Path): Path to the directory containing the tiff files
        zarr_path (Path): path to the zarr file to write the output to
        zarr_group (Path): group within the zarr store to write the data to
    """
    # get data dimensions
    files = sorted(tiff_path.glob("*.tif"))
    logger.info("%s time points found.", len(files))
    example_image = tifffile.imread(files[0])
    data_shape = (len(files), *example_image.shape)
    data_dtype = example_image.dtype
    # prepare zarr
    zarr_path.mkdir(parents=True, exist_ok=True)
    store = zarr.NestedDirectoryStore(zarr_path)
    zarr_array = zarr.open(
        store=store,
        mode="w",
        path=zarr_group,
        shape=data_shape,
        dtype=data_dtype,
    )
    # load and save data in zarr
    max_label = 0
    for t, file in enumerate(files):
        frame = tifffile.imread(file)
        if relabel:
            frame[frame != 0] += max_label
            max_label = int(np.max(frame))
        zarr_array[t] = frame
        file.unlink()
    tiff_path.rmdir()
