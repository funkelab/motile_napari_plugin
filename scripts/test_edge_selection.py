from rtree import index
from scipy.spatial import KDTree
import numpy as np
import napari
import zarr

from motile_plugin import MotileWidget
from napari.utils.theme import _themes
from napari.layers.points._points_utils import create_box
from napari_graph import UndirectedGraph
import pandas as pd
from napari.layers import Graph
import time

_themes["dark"].font_size = "18pt"

def build_graph(n_nodes: int, n_neighbors: int, n_dims=2) -> UndirectedGraph:
    neighbors = np.random.randint(n_nodes, size=(n_nodes * n_neighbors))
    edges = np.stack([np.repeat(np.arange(n_nodes), n_neighbors), neighbors], axis=1)
    for edge in edges:
        if edge[0] == edge[1]:
            print("SELF EDGE DETECTED: incrementing")
            edge[1] = edge[1] + 1 % n_nodes

    nodes_df = pd.DataFrame(
        400 * np.random.uniform(size=(n_nodes, n_dims)),
        columns=["t", "z", "y", "x"][-n_dims:],
    )
    graph = UndirectedGraph(edges=edges, coords=nodes_df)

    return graph


def build_tree(cylinders):
    """
    Build a Tree for 3D cylinders.

    :param cylinders: List of cylinders, where each cylinder is represented as ((x1, y1, z1), (x2, y2, z2), radius).
    :return: KDTree object.
    """
    # Example usage:
    # cylinders = [((0,0,0), (1,1,1), 0.5), ((2,2,2), (3,3,3), 0.3)]
    # tree = build_kdtree(cylinders)
    start_time = time.time()
    p = index.Property()
    p.dimension = 3
    idx = index.Index(properties=p)
    bboxes = []
    
    for i, cylinder in enumerate(cylinders):
        p1, p2, radius = cylinder
        # Calculate the bounding box of the cylinder
        axis_vector = np.array(p2) - np.array(p1)
        axis_length = np.linalg.norm(axis_vector)

        if axis_length == 0:
            print("SKIPPING DEGENERATE CYLINDER")
            continue  # Skip degenerate cylinders

        axis_vector /= axis_length  # Normalize the axis vector
        orthogonal_vector = np.array([1, 0, 0]) if axis_vector[0] < 0.9 else np.array([0, 1, 0])
        ortho1 = np.cross(axis_vector, orthogonal_vector)
        ortho2 = np.cross(axis_vector, ortho1)

        corner_points = [p1, p2]
        for ortho in [ortho1, ortho2]:
            for sign in [-1, 1]:
                direction = ortho * radius * sign
                corner_points.extend([p1 + direction, p2 + direction])

        min_bounds = np.min(corner_points, axis=0)
        max_bounds = np.max(corner_points, axis=0)
        bbox = tuple(min_bounds) + tuple(max_bounds)
        bboxes += [bbox]

        # Insert the bounding box into the R-tree
        idx.insert(i, bbox)
    end_time = time.time()
    print(f"Took {end_time - start_time} seconds to build RTree with {len(cylinders)} cylinders")
    # Build and return the KD-Tree
    return idx, bboxes

def create_cylinders(graph, radius=5):
    # For undirected graphs, this currently adds each edge twice
    # Because I couldn't figure out how to iterate the edges properly
    # Could use buffer??? graph.edges buffer skipping code
    cylinders = []
    for edge_set in graph.get_edges():
        for edge in edge_set:
            # print(f"Edge: {edge}")
        # (start_node, end_node) = edge[0]
        # cylinders += [(graph.get_coordinates()[start_node], graph.get_coordinates()[end_node], cylinder_radius)]
            coords = graph.get_coordinates(edge)
            # Coords should have shape (2, ndim)

            # print(f"Coords: {coords} shape {coords.shape}")
            if coords.shape[1] == 2:
                # add dummy third dimension to endpoints
                coords = np.c_[np.zeros(2), coords]

            # print(f"New coords: {coords} shape {coords.shape}")
            cylinders += [(coords[0,:], coords[1,:],  radius)]
    return cylinders


def ray_intersects_cylinder(ray_origin, ray_direction, cylinder, tolerance=1e-6):
    """
    Check if a ray intersects with a cylinder.

    :param ray_origin: Origin of the ray (x, y, z).
    :param ray_direction: Direction of the ray (dx, dy, dz).
    :param cylinder: Cylinder defined as ((x1, y1, z1), (x2, y2, z2), radius).
    :param tolerance: Numerical tolerance for the intersection test.
    :return: Boolean indicating if there is an intersection.
    """
    p1, p2, radius = cylinder
    d = np.array(p2) - np.array(p1)
    m = np.array(ray_origin) - np.array(p1)
    n = np.array(ray_direction)

    md = np.dot(m, d)
    nd = np.dot(n, d)
    dd = np.dot(d, d)

    # Coefficients for the quadratic equation
    a = dd * np.dot(n, n) - nd * nd
    b = dd * np.dot(n, m) - nd * md
    c = dd * np.dot(m, m) - md * md - radius * radius * dd

    # If a is approximately zero, the ray is parallel to the cylinder axis
    if abs(a) < tolerance:
        return False

    # Quadratic formula discriminant
    discr = b * b - a * c

    # If discriminant is negative, no real roots - no intersection
    if discr < 0:
        return False

    # Ray intersects cylinder
    return True

def distance_to_bbox(ray_origin, bbox):
    """
    Calculate the distance from a point to the closest point on a bounding box.

    :param ray_origin: Origin of the ray (x, y, z).
    :param bbox: Bounding box represented as a tuple (xmin, ymin, zmin, xmax, ymax, zmax).
    :return: Distance from the ray origin to the closest point on the bounding box.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    closest_point = np.maximum(np.minimum(ray_origin, [xmax, ymax, zmax]), [xmin, ymin, zmin])
    return np.linalg.norm(ray_origin - closest_point)


def query_ray_intersection(ray_origin, ray_direction, cylinders, rtree_index, bboxes):
    """
    Query the R-tree for a ray intersection with cylinders.

    :param ray_origin: Origin of the ray (x, y, z).
    :param ray_direction: Direction of the ray (dx, dy, dz).
    :param cylinders: List of cylinders.
    :param rtree_index: R-tree index object.
    :return: Index of the intersecting cylinder or None.
    """
    # Define a large bounding box along the ray for querying the R-tree
    ray_point_far = np.array(ray_origin) + np.array(ray_direction) * 10000  # Arbitrary large number
    bbox = tuple(np.minimum(ray_origin, ray_point_far)) + tuple(np.maximum(ray_origin, ray_point_far))

    # Query the R-tree for intersecting bounding boxes
    candidates = list(rtree_index.intersection(bbox))
    candidates.sort(key=lambda idx: distance_to_bbox(ray_origin, bboxes[idx]))
    
    for idx in candidates:
        if ray_intersects_cylinder(ray_origin, ray_direction, cylinders[idx]):
            return idx  # Return the first intersecting cylinder's index

    return None  # No intersection found

if __name__ == "__main__":
    # Create example graph
    n_dims = 3
    n_nodes = 100
    n_neighbors = 1
    start_time = time.time()
    example_graph = build_graph(n_nodes, n_neighbors, n_dims=n_dims)
    end_time = time.time()
    print(f"Took {end_time - start_time} second to build napari graph with {n_nodes} nodes and {n_neighbors * n_nodes} edges")

    # Initialize Napari viewer
    viewer = napari.Viewer()
    graph_layer = Graph(data=example_graph, name=f"{n_dims}D Graph")
    viewer.add_layer(graph_layer)

    # Put edges into KD Tree
    # Currently this includes all edges, without consideration for the view
    # TODO: Should also link rtree to dims changes and rebuild the tree based on the currently visible edges
    edge_width = 2 # TODO: this should be linked to the view
    cylinders = create_cylinders(example_graph, radius=edge_width)
    print(f"{len(cylinders)} cylinders created")
    tree, bboxes = build_tree(cylinders)

    print(f"Tree {tree}")
    # print(f"BBoxes {bboxes}")

    # Instead of proper highlighting, we just add points layer with endpoints in red
    edge_selection_layer = viewer.add_points([], size=10, face_color='red', ndim=n_dims, name="Selection Endpoints")

    # Add callback to graph layer on click to select edge
    @graph_layer.mouse_drag_callbacks.append
    def on_click(layer, event):
        near_point, far_point = layer.get_ray_intersections(
            np.array(event.position),
            event.view_direction,
            event.dims_displayed
        )
        print(f"Near point {near_point} far point {far_point}")
        if len(event.dims_displayed) == 3:        
            ray_origin = near_point
            ray_direction = event.view_direction
        else:
            # 2D case
            ray_origin = list([0] + [event.position[dim] for dim in event.dims_displayed])
            ray_direction = list([1, 0, 0])

        if ray_origin is None:
            edge_selection_layer.data = []
            return
        result_id = query_ray_intersection(ray_origin, ray_direction, cylinders, tree, bboxes)

        print(f"on_click: ray origin {ray_origin} result id {result_id}")
        if result_id:
            cylinder = cylinders[result_id]
            source = cylinder[0]
            target = cylinder[1] 
            if n_dims == 2:
                # Remove dummy first element of each coord
                source = source[1:]
                target = target[1:]
            print(f"source {source} target {target}")
            edge_selection_layer.data = np.array([source, target])
        else:
            edge_selection_layer.data = []

    # Start the Napari GUI event loop
    napari.run()
