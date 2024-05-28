import logging
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import tifffile
import zarr
from appdirs import AppDirs
from napari.types import LayerData

logger = logging.getLogger(__name__)


def Fluo_N2DL_HeLa() -> list[LayerData]:
    """Loads the Fluo-N2DL-HeLa 01 training raw data and silver truth from
    the appdir "user data dir". Will download it from the CTC and convert it to
    zarr if it is not present already.
    Returns:
        list[LayerData]: An image layer of 01 training raw data and a labels
            layer of 01 training silver truth labels
    """
    ds_name = "Fluo-N2DL-HeLa"
    appdir = AppDirs("motile-plugin")
    data_dir = Path(appdir.user_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return read_ctc_dataset(ds_name, data_dir)


def read_ctc_dataset(ds_name: str, data_dir: Path) -> list[LayerData]:
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

    raw_data = zarr.open(store=ds_zarr, path="01", dimension_separator="/")[:]
    raw_layer_data = (raw_data, {"name": "01_raw"}, "image")
    seg_data = zarr.open(ds_zarr, path="01_ST", dimension_separator="/")[:]
    seg_layer_data = (seg_data, {"name": "01_ST"}, "labels")
    return [raw_layer_data, seg_layer_data]


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
    convert_to_zarr(ds_dir / "01_ST" / "SEG", ds_zarr, "01_ST")
    shutil.rmtree(ds_dir)


def convert_to_zarr(tiff_path: Path, zarr_path: Path, zarr_group: str):
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
    for t, file in enumerate(files):
        image = tifffile.imread(file)
        zarr_array[t] = image
        file.unlink()
    tiff_path.rmdir()
