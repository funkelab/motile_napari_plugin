Getting started with the motile plugin
======================================

Installation
------------
This plugin depends on ``ilpy``, which must be installed via conda.::

    conda create -n motile-plugin python=3.10
    conda activate motile-plugin
    conda install -c conda-forge -c funkelab -c gurobi ilpy
    pip install motile-plugin

If this is successful, you can then run ``napari`` from your command line, and
the motile plugin should be visible in the ``Plugins`` drop down menu.
Clicking this should open the motile widget on the right of the viewer.

Input data
----------
The motile plugin does not perform detection: you must provide a Labels layer or a Points layer
containing the objects you want to track.
The Labels layer must have time as the
first dimension followed by the spatial dimensions (no channels).
You can load an example Labels layer of a 2D HeLa dataset from the `Cell Tracking Challenge`_
in ``Files`` -> ``Sample Data`` -> ``Fluo-N2DL-HeLa (Motile)``.
The Points layer must have the point locations with time as the first number,
followed by the spatial dimensions. While source images are
nice to qualitatively evaluate results, they are not necessary to run tracking.

In the future, we could also support Shapes layers as input (for example,
for bounding box tracking) - please react to
`Issue #48`_ if this is important to your use case, and give feedback on what type
of shape linking you want.

Running tracking
----------------
The motile plugin by default opens to the ``Run Editor`` view. In this section,
you can pick a name for your run, select an input layer, set
hyperparameters, and start a motile run. Hovering over the title of each
element in the widget will make a tooltip appear describing the purpose
of the element. When you are ready, click the ``Run Tracking`` button to start tracking.

Viewing run results
-------------------
Clicking the ``Run Tracking`` button will automatically take you to the ``Run Viewer``.
It contains the following:

- The ``Solver status`` label, which will display if the solver is in progress or
  done solving.
- The ``Graph of solver gap``, which is mostly for debugging purposes.
  The solver gap is an optimization value that should decrease at each iteration.
- The run settings, including ``Hyperparameters``, ``Costs``, and ``Attribute weights``.
- The ``Save run`` button. This button will take you to a file dialog to save the
  whole run, so that if you close napari and re-open it, you can load the run
  and see the results.
- The ``Export tracks to CSV`` button, which will take you to a file dialog for saving
  a csv file containing the tracks. If your input was a Labels layer, the
  ``node_id`` will be determined by the time and the original segmentation label id.
  If your input was a Points layer, the ``node_id`` is simply the index of the
  node in the list of points.
    - Note: This does not save the output segmentation. If you want to save
  the relabeled segmentation, you can do so through napari by selecting the
  layer and then selecting ``File``-> ``Save selected layers``
- The ``Back to editing`` button, which will return you to the ``Run Editor`` in its
  previous state.
- The ``Edit this run`` button. This button will take you back to the ``Run Editor``,
  but will overwrite the previous settings with the settings of the run you are
  viewing.

Once the solver completes, you will also see a tracks layer
in the napari viewer. If your input was a segmentation, there will also be
a new segmentation layer where the IDs have been relabeled to match across time.

A list of ``Tracking Runs`` will also appear at the bottom of the widget.
These are the runs that are stored in memory - if you run tracking multiple
times with different inputs or parameters, you can click back and forth
between the results here. Deleting runs you do not want to keep viewing
is a good idea, since these are stored in memory. Runs that were saved in
previous sessions do not appear here until you load them from disk with the
``Load Run`` button.


.. _Issue #48: https://github.com/funkelab/motile_napari_plugin/issues/48
.. _Cell Tracking Challenge: https://celltrackingchallenge.net/
