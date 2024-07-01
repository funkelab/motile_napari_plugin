from napari.layers import Graph
from napari_graph import UndirectedGraph


def get_location(node_data, loc_key="pos"):
    return node_data[loc_key]


def to_napari_graph_layer(graph, name, loc_key="pos"):
    """A function to convert a networkx graph into a Napari Graph layer"""
    nx_id_to_napari_id = {}
    napari_id_to_nx_id = {}
    napari_id = 0
    for nx_id in graph.nodes:
        nx_id_to_napari_id[nx_id] = napari_id
        napari_id_to_nx_id[napari_id] = nx_id
        napari_id += 1
    num_nodes = napari_id

    edges = [
        [nx_id_to_napari_id[s], nx_id_to_napari_id[t]]
        for s, t in graph.edges()
    ]
    coords = []
    for nap_id in range(num_nodes):
        pos = get_location(
            graph.nodes[napari_id_to_nx_id[nap_id]], loc_key=loc_key
        )
        time = graph.nodes[napari_id_to_nx_id[nap_id]]["time"]
        coords.append(
            [
                time,
            ]
            + list(pos)
        )
    ndim = len(coords[0])  # TODO: empty graph?
    napari_graph = UndirectedGraph(edges=edges, coords=coords, ndim=ndim)
    graph_layer = Graph(data=napari_graph, name=name)
    graph_layer.projection_mode = "all"
    return graph_layer
