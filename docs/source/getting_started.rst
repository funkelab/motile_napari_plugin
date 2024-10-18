Getting started with the motile plugin
======================================

Installation
************
This plugin depends on ``ilpy``, which must be installed via conda.::

    conda create -n motile-plugin python=3.10
    conda activate motile-plugin
    conda install -c conda-forge -c funkelab -c gurobi ilpy
    pip install motile-plugin

If this is successful, you can then run ``napari`` from your command line, and
the motile plugin should be visible in the ``Plugins`` drop down menu.
Clicking the Main Motile Widget should open the menu widget on the right of the viewer,
and a lineage tree view in the bottom of the viewer.

Tutorial video
**************
This video walks through tracking an example dataset from the `Cell Tracking Challenge`_,
covering most of the same information as the rest of this getting started guide.

.. raw:: html

  <iframe src="https://drive.google.com/file/d/1zHvO9inHw0Hlbwq5zmRX4qUnVuO21neo/preview" width="640" height="480" allow="autoplay"></iframe>


Input data
**********
The motile plugin does not perform detection: you must provide a Labels layer or a Points layer
containing the objects you want to track.
The Labels layer must have time as the
first dimension followed by the spatial dimensions (no channels).
The Points layer must have the point locations with time as the first number,
followed by the spatial dimensions. While source images are
nice to qualitatively evaluate results, they are not necessary to run tracking.

There are two example datasets provided in ``File`` -> ``Open Sample`` -> ``Motile``.
A 2D HeLa dataset from the `Cell Tracking Challenge`_ is provided, both in full and a cropped subset for testing features on smaller data, and has both a Labels layer and Points layer.
There is also a 3D dataset of images and segmentations of a membrane-labeled developing early mouse embryo (4-26 cells)
from `Fabrèges et al (2024)`_, automatically downloaded from `zenodo`_.

In the future, we could also support Shapes layers as input (for example,
for bounding box tracking) - please react to
`Issue #48`_ if this is important to your use case, and give feedback on what type
of shape linking you want.

Plugin widgets
**************
You can open the Main Motile Widget via ``Plugins`` -> ``Motile`` -> ``Motile Main Widget``.
This will open a tab widget containing a ``Motile``, ``Edit Tracks``, and ``Results List`` widget, as well
as an empty ``Lineage View`` widget at the bottom of the screen. Alternatively, you can open the Tree View
and the Menus widgets individually under ``Plugins`` -> ``Motile`` and dock them manually.

Running tracking
****************
The ``Motile`` tab by default opens to the ``Run Editor`` view. In this view,
you can pick a name for your run, select an input layer, set
hyperparameters, and start a motile run. Hovering over the title of each
element in the widget will make a tooltip appear describing the purpose
of the element. All hyperparameters are explained in the :doc:`tracking with motile <motile>` docs page.
When you are ready, click the ``Run Tracking`` button to start tracking.

Viewing and editing run results
*******************************
Clicking the ``Run Tracking`` button will automatically take you to the motile ``Run Viewer``
menu, display a points and a tracks layer in the napari viewer, and populate the Lineage Tree view. If your input was a segmentation, there will also be
a new segmentation layer where the IDs have been relabeled to match across time, and the input segmentation layer will be hidden to avoid confusion.

You can :doc:`view the results <tree_view>` using the synchronized napari layers and tree view, and :doc:`edit the detections and links <editing>` to correct any mistakes that you find. You can also re-run the tracking step with different parameters. Re-running the motile tracking will only take into account the detection corrections
if you select the new labels/points layer as input: our next major feature to add
is incorporating the detection and linking corrections into the optimization task in a more principled manner.

Each ``Tracking Run`` will be stored in the ``Results List`` widget.
These are the runs that are stored in memory - if you run tracking multiple
times with different inputs or parameters, you can click back and forth
between the results here. Here you can also save any runs that you want to store for later.
Deleting runs you do not want to keep viewing is a good idea, since these are stored in memory.
Runs that were saved in previous sessions do not appear here until you load them from disk with the ``Load Tracks`` button.
The tracking results can also be visualized as a lineage tree.
You can open the lineage tree widget via ``Plugins`` > ``Motile`` > ``Lineage View``.
For more details, go to the :doc:`Tree View <tree_view>` documentation.

.. _Issue #48: https://github.com/funkelab/motile_napari_plugin/issues/48
.. _Cell Tracking Challenge: https://celltrackingchallenge.net/
.. _Fabrèges et al (2024): https://www.science.org/doi/10.1126/science.adh1145
.. _zenodo: https://zenodo.org/records/13903500
