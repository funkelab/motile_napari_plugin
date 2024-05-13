Getting started with the motile plugin
======================================

Installation
------------
This plugin depends on ``ilpy``, which must be installed via conda.::

    conda create -n motile-plugin python=3.10
    conda activate motile-plugin
    conda install -c conda-forge -c funkelab -c gurobi ilpy
    pip install git+https://github.com/funkelab/motile-napari-plugin.git

If this is successful, you can then run ``napari`` from your command line, and
the motile plugin should be visible in the "Plugins" drop down menu.
Clicking this should open the motile widget on the right of the viewer.

Input data
----------
The motile plugin takes as input expects a Labels layer with time as the
first dimension followed by the spatial dimensions (no channels).
You can load an example 2D HeLa Dataset from the `Cell Tracking Challenge`_ 
in "Files" -> "Sample Data".

In the future, we could also support Points layers as input - please react to 
`Issue #30`_ if this is important to your use case. While source images are 
nice to qualitatively evaluate results, they are not necessary to run tracking. 

Running tracking
----------------
The motile plugin by default opens to the "Run Editor" view. In this section,
you can pick a name for your run, select an input Labels layer, set
hyperparameters, and start a motile run. Hovering over the title of each
element in the widget will make a tooltip appear describing the purpose
of the element. When you are ready, click the "Run" button to start tracking.

Viewing run results
-------------------
Clicking the "Run" button will automatically take you to the "Run Viewer".
Here you will see:

- the solver status
- a graph of the solver gap (an optimization value that should approach zero)
- the hyperparameters of the run
- a button to save the whole run (for persistent viewing in the plugin)
- a button to export just the tracks as a CSV
- a button to return to the Run Editor

Once the solver completes, you will also see a segmentation and a tracks layer
in the napari viewer. These are the tracking results.

A list of "Tracking Runs" will also appear at the bottom of the widget.
These are the runs that are stored in memory - if you run tracking multiple
times with different inputs or parameters, you can click back and forth
between the results here. Deleting runs you do not want to keep viewing
is a good idea, since these are stored in memory. Runs that were saved in 
previous sessions do not appear here until you load them from disk with the 
"Load Run" button.


.. _Issue #30: https://github.com/funkelab/motile-napari-plugin/issues/30
.. _Cell Tracking Challenge: https://celltrackingchallenge.net/