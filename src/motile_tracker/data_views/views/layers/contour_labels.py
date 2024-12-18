from __future__ import annotations

import functools
from typing import Optional

import napari
import numpy as np
from napari.layers.labels._labels_utils import (
    expand_slice,
)
from napari.utils import DirectLabelColormap
from scipy import ndimage as ndi


def get_contours(
    labels: np.ndarray,
    thickness: int,
    background_label: int,
    group_labels: list[int] | None = None,
):
    """Computes the contours of a 2D label image.

    Parameters
    ----------
    labels : array of integers
        An input labels image.
    thickness : int
        It controls the thickness of the inner boundaries. The outside thickness is always 1.
        The final thickness of the contours will be `thickness + 1`.
    background_label : int
        That label is used to fill everything outside the boundaries.

    Returns
    -------
    A new label image in which only the boundaries of the input image are kept.
    """
    struct_elem = ndi.generate_binary_structure(labels.ndim, 1)

    thick_struct_elem = ndi.iterate_structure(struct_elem, thickness).astype(bool)

    dilated_labels = ndi.grey_dilation(labels, footprint=struct_elem)
    eroded_labels = ndi.grey_erosion(labels, footprint=thick_struct_elem)
    not_boundaries = dilated_labels == eroded_labels

    contours = labels.copy()
    contours[not_boundaries] = background_label

    # instead of filling with background label, fill the group label with their normal color
    if group_labels is not None and len(group_labels) > 0:
        group_mask = functools.reduce(
            np.logical_or, (labels == val for val in group_labels)
        )
        combined_mask = not_boundaries & group_mask
        contours = np.where(combined_mask, labels, contours)

    return contours


class ContourLabels(napari.layers.Labels):
    """Extended labels layer that allows to show contours and filled labels simultaneously"""

    @property
    def _type_string(self) -> str:
        return "labels"  # to make sure that the layer is treated as labels layer for saving

    def __init__(
        self,
        data: np.array,
        name: str,
        opacity: float,
        scale: tuple,
        colormap: DirectLabelColormap,
    ):
        super().__init__(
            data=data,
            name=name,
            opacity=opacity,
            scale=scale,
            colormap=colormap,
        )

        self.group_labels = None

    def _calculate_contour(
        self, labels: np.ndarray, data_slice: tuple[slice, ...]
    ) -> Optional[np.ndarray]:
        """Calculate the contour of a given label array within the specified data slice.

        Parameters
        ----------
        labels : np.ndarray
            The label array.
        data_slice : Tuple[slice, ...]
            The slice of the label array on which to calculate the contour.

        Returns
        -------
        Optional[np.ndarray]
            The calculated contour as a boolean mask array.
            Returns None if the contour parameter is less than 1,
            or if the label array has more than 2 dimensions.
        """
        if self.contour < 1:
            return None
        if labels.ndim > 2:
            return None

        expanded_slice = expand_slice(data_slice, labels.shape, 1)
        sliced_labels = get_contours(
            labels[expanded_slice],
            self.contour,
            self.colormap.background_value,
            self.group_labels,
        )

        # Remove the latest one-pixel border from the result
        delta_slice = tuple(
            slice(s1.start - s2.start, s1.stop - s2.start)
            for s1, s2 in zip(data_slice, expanded_slice, strict=False)
        )
        return sliced_labels[delta_slice]
