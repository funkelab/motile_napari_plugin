import numpy as np
import tifffile
import zarr
import os
from skimage.filters import threshold_otsu
from scipy.ndimage import label

# Step 1: Read the TIFF files
directory = "/Users/kharrington/git/cmalinmayor/motile-plugin/data/Fluo-N2DL-HeLa/01"
zarr_directory = "/Users/kharrington/git/cmalinmayor/motile-plugin/data/zarr_data.zarr"
file_names = sorted([f for f in os.listdir(directory) if f.endswith('.tif')])

# Step 2: Combine them into a 3D array
images = [tifffile.imread(os.path.join(directory, fname)) for fname in file_names]
stack = np.stack(images, axis=0)

# Step 3: Create a Zarr group and save the combined array
zarr_group = zarr.open_group(zarr_directory, mode='w')
zarr_group.create_dataset("stack", data=stack, chunks=(1, *stack.shape[1:]), dtype=stack.dtype)

# Step 4: Apply Otsu thresholding to create a segmentation mask
threshold_value = threshold_otsu(stack)
segmentation_mask = stack > threshold_value

# Step 5: Apply connected components to each slice of the segmentation mask
labeled_slices = [label(slice)[0] for slice in segmentation_mask]
labeled_stack = np.stack(labeled_slices, axis=0)

# Step 6: Save the segmentation mask and labeled stack in the Zarr group
zarr_group.create_dataset("segmentation_mask", data=segmentation_mask, chunks=(1, *segmentation_mask.shape[1:]), dtype=segmentation_mask.dtype)
zarr_group.create_dataset("labeled_stack", data=labeled_stack, chunks=(1, *labeled_stack.shape[1:]), dtype=labeled_stack.dtype)

print("Processing complete. Data saved in Zarr format.")
