from motile_plugin.data_model import SolutionTracks


def test_export_to_csv(graph_2d, graph_3d, tmp_path):
    tracks = SolutionTracks(graph_2d, ndim=3)
    temp_file = tmp_path / "test_export_2d.csv"
    tracks.export_tracks(temp_file)
    with open(temp_file) as f:
        lines = f.readlines()

    assert len(lines) == tracks.graph.number_of_nodes() + 1  # add header

    header = ["t", "y", "x", "id", "parent_id", "track_id"]
    assert lines[0].strip().split(",") == header

    tracks = SolutionTracks(graph_3d, ndim=4)
    temp_file = tmp_path / "test_export_3d.csv"
    tracks.export_tracks(temp_file)
    with open(temp_file) as f:
        lines = f.readlines()

    assert len(lines) == tracks.graph.number_of_nodes() + 1  # add header

    header = ["t", "z", "y", "x", "id", "parent_id", "track_id"]
    assert lines[0].strip().split(",") == header
