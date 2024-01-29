from rtree import index
from scipy.spatial import KDTree
import numpy as np

def build_tree(cylinders):
    """
    Build a Tree for 3D cylinders.

    :param cylinders: List of cylinders, where each cylinder is represented as ((x1, y1, z1), (x2, y2, z2), radius).
    :return: KDTree object.
    """
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

    # Build and return the KD-Tree
    return idx, bboxes

# Example usage:
# cylinders = [((0,0,0), (1,1,1), 0.5), ((2,2,2), (3,3,3), 0.3)]
# tree = build_kdtree(cylinders)


# TODO dont hardcode graph
graph = viewer.layers[-1].data

cylinder_radius = 5
cylinders = []
for edge in graph.get_edges():
    (start_node, end_node) = edge[0]
    # cylinders += [(graph.get_coordinates()[start_node], graph.get_coordinates()[end_node], cylinder_radius)]
    coords = graph.get_coordinates(edge[0])
    
    cylinders += [(coords[0,:], coords[1,:],  cylinder_radius)]

tree, bboxes = build_tree(cylinders)




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

# Example usage:
ray_origin = (2, 367, 514)
ray_direction = (0, 1, 0)
result = query_ray_intersection(ray_origin, ray_direction, cylinders, tree, bboxes)

(result, cylinders[result])


