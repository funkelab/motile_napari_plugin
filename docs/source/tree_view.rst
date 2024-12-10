Tree View
=========

Usage Overview
**************
In addition to performing tracking with motile, this plugin also provides the ability to
visualize tracks (and segmentations) in napari, through a lineage tree view and
synchronized points, segmentation, and tracks layers. To visualize results generated
through the motile widget in the tree view, you can open the tree widget from the UI
via ``Plugins`` > ``Motile`` > ``Lineage View``.

Clicking on individual nodes in the tree widget or in the napari Points or Labels layer will select that node,
highlighting it both in the tree view and in the napari layers, and centering the view if necessary.
You can navigate and select nodes in the tree view using the arrow keys (make sure to click on the tree widget first).
Optionally, you can display only selected lineages in the tree view and/or napari layers (press ``Q`` in the tree widget and/or in the napari viewer).
If you used a Labels layer as input for tracking, you will also have the option to plot the object sizes (area or volume) in calibrated units
(make sure that your input layer has the correct scaling before starting the tracking).
Please visit :doc:`key bindings <key_bindings>` page for a complete list of available key bindings in the napari viewer and in the tree view.

Viewing Externally Generated Tracks
***********************************
It is also possible to view tracks that were not created from the motile widget using
the synchronized Tree View and napari layers. To do so, navigate to the ``Results List`` tab and select ``External tracks from CSV`` in the dropdown menu at the bottom of the widgets, and click ``Load``.
A pop up menu will allow you to select a CSV file and map its columns to the required default attributes and optional additional attributes. You may also provide the accompanying segmentation and specify scaling information.

The following columns have to be selected:

- time: representing the position of the object in the time dimension.
- x: x centroid coordinate of the object.
- y: y centroid coordinate of the object.
- z (optional): z centroid coordinate of the object, if it is a 3D object.
- id: unique id of the object.
- parent_id: id of the directly connected predecessor (parent) of the object. Should be empty if the object is at the start of a lineage.
- seg_id: label value in the segmentation image data (if provided) that corresponds to the object id.

From this, a `SolutionTracks object`_ is generated, containing a networkx graph representing the tracking result, and optionally
a segmentation. The networkx graph is directed, with nodes representing detections and
edges going from a detection in time t to the same object in t+1 (edges go forward in time).
Nodes must have an attribute representing time, by default named "time" but a different name
can be stored in the ``Tracks.time_attr`` attribute. Nodes must also have one or more attributes
representing position. The default way of storing positions on nodes is an attribute called
"pos" containing a list of position values, but dimensions can also be stored in separate attributes
(e.g. "x" and "y", each with one value). The name or list of names of the position attributes
should be specified in ``Tracks.pos_attr``. If a segmentation is provided but no ``area`` attribute, it will be computed automatically.

The segmentation is expected to be a numpy array with time as the first dimension, followed
by the position dimensions in the same order as the ``Tracks.pos_attr``. If a segmentation
is provided, the nodes in the graph should also store the label id of the corresponding segmentation
in a ``seg_id`` attribute, to allow us to match nodes in the graph to their segmentations.

An example script that loads a tracks object from a CSV and segmentation array is provided in `scripts/view_external_tracks.py`. Once you have a Tracks object in the format described above,
the following lines will view it in the Tree View and create synchronized napari layers
(Points, Labels, and Tracks) to visualize the provided tracks.::

    widget = TreeWidget(viewer)
    widget.tracks_viewer.tracks_list.add_tracks(tracks, name="Example")

We plan to incorporate loaders from standard formats in the future to make this process easier,
and incorporate the loading into the user interface.

.. _SolutionTracks object: https://funkelab.github.io/motile_napari_plugin/autoapi/motile_plugin/data_model/solution_tracks/index.html
