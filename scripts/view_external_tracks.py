import napari
from motile_tracker.application_menus import MainApp
from motile_tracker.data_views.views_coordinator.tracks_viewer import TracksViewer
from motile_tracker.example_data import Fluo_N2DL_HeLa
from motile_tracker.import_export.load_tracks import tracks_from_csv

if __name__ == "__main__":
    # load the example data
    raw_layer_info, labels_layer_info, points_layer_info = Fluo_N2DL_HeLa()
    segmentation_arr = labels_layer_info[0]
    # the segmentation ids in this file correspond to the segmentation ids in the
    # example segmentation data, loaded above
    csvfile = "scripts/hela_example_tracks.csv"
    selected_columns = {
        "t": "t",
        "y": "y",
        "x": "x",
        "id": "id",
        "parent_id": "parent_id",
        "seg_id": "seg_id",
    }
    tracks = tracks_from_csv(
        csvfile,
        selected_columns,
        extra_columns={},
        segmentation=segmentation_arr,
        scale=[1, 1],
    )

    viewer = napari.Viewer()
    raw_data, raw_kwargs, _ = raw_layer_info
    viewer.add_image(raw_data, **raw_kwargs)
    labels_data, labels_kwargs, _ = labels_layer_info
    viewer.add_labels(labels_data, **labels_kwargs)
    widget = MainApp(viewer)
    viewer.window.add_dock_widget(widget)
    TracksViewer.get_instance(viewer).tracks_list.add_tracks(tracks, "example")

    # Start the Napari GUI event loop
    napari.run()
