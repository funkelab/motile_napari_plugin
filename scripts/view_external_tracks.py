import napari
from motile_plugin.example_data import Fluo_N2DL_HeLa
from motile_plugin.utils.load_tracks import tracks_from_csv
from motile_plugin.widgets import TreeWidget

if __name__ == "__main__":
    # load the example data
    raw_layer_info, labels_layer_info = Fluo_N2DL_HeLa()
    segmentation_arr = labels_layer_info[0]
    # the segmentation ids in this file correspond to the segmentation ids in the
    # example segmentation data, loaded above
    csvfile = "hela_example_tracks.csv"
    tracks = tracks_from_csv(csvfile, segmentation_arr)

    viewer = napari.Viewer()
    raw_data, raw_kwargs, _ = raw_layer_info
    viewer.add_image(raw_data, **raw_kwargs)
    labels_data, labels_kwargs, _ = labels_layer_info
    viewer.add_labels(labels_data, **labels_kwargs)
    widget = TreeWidget(viewer)
    widget.tracks_viewer.view_external_tracks(tracks, "example")
    viewer.window.add_dock_widget(widget, name="Lineage View", area="bottom")

    # Start the Napari GUI event loop
    napari.run()
