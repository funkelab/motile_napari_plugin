from napari.layers import Graph
from napari_graph import UndirectedGraph


def get_location(node_data, loc_keys=("z", "y", "x")):
    return [node_data[k] for k in loc_keys]


def to_napari_graph_layer(graph, name, loc_keys=("t", "z", "y", "x")):
    """A function to convert a networkx graph into a Napari Graph layer"""
    nx_id_to_napari_id = {}
    napari_id_to_nx_id = {}
    napari_id = 0
    for nx_id in graph.nodes:
        nx_id_to_napari_id[nx_id] = napari_id
        napari_id_to_nx_id[napari_id] = nx_id
        napari_id += 1
    num_nodes = napari_id

    edges = [[nx_id_to_napari_id[s], nx_id_to_napari_id[t]] for s, t in graph.edges()]
    coords = [
        get_location(
            graph.nodes[napari_id_to_nx_id[nap_id]], loc_keys=loc_keys
        )
        for nap_id in range(num_nodes)
    ]
    ndim = len(loc_keys)
    napari_graph = UndirectedGraph(edges=edges, coords=coords, ndim=ndim)
    graph_layer = Graph(data=napari_graph, name=name)
    return graph_layer
