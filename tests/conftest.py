import networkx as nx
import numpy as np
import pytest
from motile_toolbox.candidate_graph.graph_attributes import EdgeAttr, NodeAttr
from skimage.draw import disk


@pytest.fixture
def segmentation_2d():
    frame_shape = (100, 100)
    total_shape = (2, *frame_shape)
    segmentation = np.zeros(total_shape, dtype="int32")
    # make frame with one cell in center with label 1
    rr, cc = disk(center=(50, 50), radius=20, shape=(100, 100))
    segmentation[0][rr, cc] = 1

    # make frame with two cells
    # first cell centered at (20, 80) with label 1
    # second cell centered at (60, 45) with label 2
    rr, cc = disk(center=(20, 80), radius=10, shape=frame_shape)
    segmentation[1][rr, cc] = 1
    rr, cc = disk(center=(60, 45), radius=15, shape=frame_shape)
    segmentation[1][rr, cc] = 2

    return np.expand_dims(segmentation, 1)


@pytest.fixture
def multi_hypothesis_segmentation_2d():
    """
    Creates a multi-hypothesis version of the `segmentation_2d` fixture defined above.

    """
    frame_shape = (100, 100)
    total_shape = (
        2,
        2,
        *frame_shape,
    )  # 2 time points, 2 hypotheses layers, H, W
    segmentation = np.zeros(total_shape, dtype="int32")
    # make frame with one cell in center with label 1 (hypo 1)
    rr0, cc0 = disk(center=(50, 50), radius=20, shape=frame_shape)
    # make frame with one cell at (45, 45) with label 1 (hypo 2)
    rr1, cc1 = disk(center=(45, 45), radius=15, shape=frame_shape)

    segmentation[0, 0][rr0, cc0] = 1
    segmentation[0, 1][rr1, cc1] = 1

    # make frame with two cells
    # first cell centered at (20, 80) with label 1
    rr0, cc0 = disk(center=(20, 80), radius=10, shape=frame_shape)
    rr1, cc1 = disk(center=(15, 75), radius=15, shape=frame_shape)

    segmentation[1, 0][rr0, cc0] = 1
    segmentation[1, 1][rr1, cc1] = 1

    # second cell centered at (60, 45) with label 2
    rr0, cc0 = disk(center=(60, 45), radius=15, shape=frame_shape)
    rr1, cc1 = disk(center=(55, 40), radius=20, shape=frame_shape)

    segmentation[1, 0][rr0, cc0] = 2
    segmentation[1, 1][rr1, cc1] = 2

    return segmentation


@pytest.fixture
def graph_2d():
    graph = nx.DiGraph()
    nodes = [
        (
            "0_1",
            {
                NodeAttr.POS.value: [50, 50],
                NodeAttr.TIME.value: 0,
                NodeAttr.SEG_ID.value: 1,
                NodeAttr.AREA.value: 1245,
            },
        ),
        (
            "1_1",
            {
                NodeAttr.POS.value: [20, 80],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_ID.value: 1,
            },
        ),
        (
            "1_2",
            {
                NodeAttr.POS.value: [60, 45],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_ID.value: 2,
                NodeAttr.AREA.value: 697,
            },
        ),
    ]
    edges = [
        (
            "0_1",
            "1_1",
            {EdgeAttr.IOU.value: 0.0},
        ),
        (
            "0_1",
            "1_2",
            {EdgeAttr.IOU.value: 0.395},
        ),
    ]
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


@pytest.fixture
def multi_hypothesis_graph_2d():
    graph = nx.DiGraph()
    nodes = [
        (
            "0_0_1",
            {
                NodeAttr.POS.value: [50, 50],
                NodeAttr.TIME.value: 0,
                NodeAttr.SEG_HYPO.value: 0,
                NodeAttr.SEG_ID.value: 1,
                NodeAttr.AREA.value: 1245,
            },
        ),
        (
            "0_1_1",
            {
                NodeAttr.POS.value: [45, 45],
                NodeAttr.TIME.value: 0,
                NodeAttr.SEG_HYPO.value: 1,
                NodeAttr.SEG_ID.value: 1,
                NodeAttr.AREA.value: 697,
            },
        ),
        (
            "1_0_1",
            {
                NodeAttr.POS.value: [20, 80],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_HYPO.value: 0,
                NodeAttr.SEG_ID.value: 1,
                NodeAttr.AREA.value: 305,
            },
        ),
        (
            "1_1_1",
            {
                NodeAttr.POS.value: [15, 75],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_HYPO.value: 1,
                NodeAttr.SEG_ID.value: 1,
                NodeAttr.AREA.value: 697,
            },
        ),
        (
            "1_0_2",
            {
                NodeAttr.POS.value: [60, 45],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_HYPO.value: 0,
                NodeAttr.SEG_ID.value: 2,
                NodeAttr.AREA.value: 697,
                NodeAttr.AREA.value: 1245,
            },
        ),
        (
            "1_1_2",
            {
                NodeAttr.POS.value: [55, 40],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_HYPO.value: 1,
                NodeAttr.SEG_ID.value: 2,
            },
        ),
    ]

    edges = [
        (
            "0_0_1",
            "1_0_1",
            {EdgeAttr.IOU.value: 0.0},
        ),
        (
            "0_0_1",
            "1_1_1",
            {EdgeAttr.IOU.value: 0.0},
        ),
        (
            "0_0_1",
            "1_0_2",
            {EdgeAttr.IOU.value: 0.3931},
        ),
        (
            "0_0_1",
            "1_1_2",
            {EdgeAttr.IOU.value: 0.4768},
        ),
        (
            "0_1_1",
            "1_0_1",
            {EdgeAttr.IOU.value: 0.0},
        ),
        (
            "0_1_1",
            "1_1_1",
            {EdgeAttr.IOU.value: 0.0},
        ),
        (
            "0_1_1",
            "1_0_2",
            {EdgeAttr.IOU.value: 0.2402},
        ),
        (
            "0_1_1",
            "1_1_2",
            {EdgeAttr.IOU.value: 0.3931},
        ),
    ]
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


def sphere(center, radius, shape):
    assert len(center) == len(shape)
    indices = np.moveaxis(np.indices(shape), 0, -1)  # last dim is the index
    distance = np.linalg.norm(
        np.subtract(indices, np.asarray(center)), axis=-1
    )
    mask = distance <= radius
    return mask


@pytest.fixture
def segmentation_3d():
    frame_shape = (100, 100, 100)
    total_shape = (2, *frame_shape)
    segmentation = np.zeros(total_shape, dtype="int32")
    # make frame with one cell in center with label 1
    mask = sphere(center=(50, 50, 50), radius=20, shape=frame_shape)
    segmentation[0][mask] = 1

    # make frame with two cells
    # first cell centered at (20, 50, 80) with label 1
    # second cell centered at (60, 50, 45) with label 2
    mask = sphere(center=(20, 50, 80), radius=10, shape=frame_shape)
    segmentation[1][mask] = 1
    mask = sphere(center=(60, 50, 45), radius=15, shape=frame_shape)
    segmentation[1][mask] = 2

    return np.expand_dims(segmentation, 1)


@pytest.fixture
def multi_hypothesis_segmentation_3d():
    """
    Creates a multi-hypothesis version of the `segmentation_3d` fixture defined above.

    """
    frame_shape = (100, 100, 100)
    total_shape = (2, 2, *frame_shape)  # 2 time points, 2 hypotheses
    segmentation = np.zeros(total_shape, dtype="int32")
    # make first frame with one cell in center with label 1
    mask = sphere(center=(50, 50, 50), radius=20, shape=frame_shape)
    segmentation[0, 0][mask] = 1
    mask = sphere(center=(45, 50, 55), radius=20, shape=frame_shape)
    segmentation[0, 1][mask] = 1

    # make second frame, first hypothesis with two cells
    # first cell centered at (20, 50, 80) with label 1
    # second cell centered at (60, 50, 45) with label 2
    mask = sphere(center=(20, 50, 80), radius=10, shape=frame_shape)
    segmentation[1, 0][mask] = 1
    mask = sphere(center=(60, 50, 45), radius=15, shape=frame_shape)
    segmentation[1, 0][mask] = 2

    # make second frame, second hypothesis with one cell
    # first cell centered at (15, 50, 70) with label 1
    # second cell centered at (55, 55, 45) with label 2
    mask = sphere(center=(15, 50, 70), radius=10, shape=frame_shape)
    segmentation[1, 1][mask] = 1

    return segmentation


@pytest.fixture
def graph_3d():
    graph = nx.DiGraph()
    nodes = [
        (
            "0_1",
            {
                NodeAttr.POS.value: [50, 50, 50],
                NodeAttr.TIME.value: 0,
                NodeAttr.SEG_ID.value: 1,
            },
        ),
        (
            "1_1",
            {
                NodeAttr.POS.value: [20, 50, 80],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_ID.value: 1,
            },
        ),
        (
            "1_2",
            {
                NodeAttr.POS.value: [60, 50, 45],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_ID.value: 2,
            },
        ),
    ]
    edges = [
        ("0_1", "1_1"),
        ("0_1", "1_2"),
    ]
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


@pytest.fixture
def multi_hypothesis_graph_3d():
    graph = nx.DiGraph()
    nodes = [
        (
            "0_0_1",
            {
                NodeAttr.POS.value: [50, 50, 50],
                NodeAttr.TIME.value: 0,
                NodeAttr.SEG_HYPO.value: 0,
                NodeAttr.SEG_ID.value: 1,
            },
        ),
        (
            "0_1_1",
            {
                NodeAttr.POS.value: [45, 50, 55],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_HYPO.value: 1,
                NodeAttr.SEG_ID.value: 1,
            },
        ),
        (
            "1_0_1",
            {
                NodeAttr.POS.value: [20, 50, 80],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_HYPO.value: 0,
                NodeAttr.SEG_ID.value: 1,
            },
        ),
        (
            "1_0_2",
            {
                NodeAttr.POS.value: [60, 50, 45],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_HYPO.value: 0,
                NodeAttr.SEG_ID.value: 2,
            },
        ),
        (
            "1_1_1",
            {
                NodeAttr.POS.value: [15, 50, 70],
                NodeAttr.TIME.value: 1,
                NodeAttr.SEG_HYPO.value: 1,
                NodeAttr.SEG_ID.value: 1,
            },
        ),
    ]
    edges = [
        ("0_0_1", "1_0_1"),
        ("0_0_1", "1_0_2"),
        ("0_1_1", "1_0_1"),
        ("0_1_1", "1_0_2"),
        ("0_0_1", "1_1_1"),
        ("0_1_1", "1_1_1"),
    ]
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph
