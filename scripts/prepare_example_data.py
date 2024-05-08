import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import tifffile
import zarr


def download_hela_dataset(data_dir: Path):
    """Download the Fluo-N2DL-HeLa dataset from the Cell Tracking Challenge
    and unzip it.
    """
    path = "http://data.celltrackingchallenge.net/training-datasets/Fluo-N2DL-HeLa.zip"
    zip_filename = data_dir / "Fluo-N2DL-HeLa.zip"
    urlretrieve(path, filename=zip_filename)
    with zipfile.ZipFile(zip_filename, "r") as zip_ref:
        zip_ref.extractall(data_dir)
    zip_filename.unlink()


def convert_to_zarr(tif_path: Path, zarr_path: Path, zarr_group: str):
    """Convert tiff file image data to zarr"""
    # get data dimensions
    files = sorted(tif_path.glob("*.tif"))
    print(f"{len(files)} time points found.")
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


if __name__ == "__main__":
    data_dir = Path("../data")
    hela_dir = data_dir / "Fluo-N2DL-HeLa"
    hela_zarr = data_dir / "Fluo-N2DL-HeLa.zarr"
    download_hela_dataset(data_dir)
    convert_to_zarr(hela_dir / "01", hela_zarr, "01")
    convert_to_zarr(hela_dir / "01_ST" / "SEG", hela_zarr, "01_ST")
