Tracking with motile
=================

Motile Parameters
*****************

Hyperparameters
---------------
The hyperparameters set up constraints on the optimization problem.
These constraints will never be violated by the solution.

- ``Max Move Distance`` - The maximum distance an object center can move between time frames, in scaled units. This should be an upper bound, as nothing further will be connected.
- ``Max Children`` - The maximum number of objects in the next time frames that an object can be linked to. Set this to 1 for tracking problems without divisions.

Constant Costs
--------------
The constant costs contribute to the objective function that the optimization
problem will minimize. They are the same for all possible links in the
tracking problem, and should be set based on general properties of the problem.
Unchecking the checkbox will not include the cost in the objective at all,
while changing the weight values will change how much each cost contributes
to the objective.

- ``Edge Selection`` - A cost for linking any two objects between time frames. If you do not have many false positive detections, this value should be quite negative to encourage selecting as many linking edges as possible. If none of your costs are negative, the objective function will be minimized by selecting nothing (which has cost 0), so this cost can control generally how many edges/links are selected.
- ``Appear`` - A cost for starting a new track. Assuming tracks should be long and continuous, the appear cost should be positive. A high appear cost encourages continuing tracks where possible, but can lead to not selecting short tracks at all.
- ``Division`` - A cost for dividing, where a higher division cost will lead to fewer divisions. If your task does not have divisions, this cost does not matter - you can un-check it for clarity, but including it will do nothing.

Attribute weights
-----------------
The attribute-based costs also contribute to the objective function that
the optimizer will minimize. Every possible link in the tracking problem
will have a different cost based on the specific attributes (distance or IoU)
of that pair of detections. Unchecking the checkbox will not include the
feature in the objective. The user-provided weight values will be multiplied by
the attribute values to generate the cost for linking a specific pair of
detections.

- ``Distance`` - Use the distance between objects as a feature for linking. The provided weight will be multiplied by the distance between objects to get the cost for linking the two objects. This weight should usually be positive, so that higher distances are more costly.
- ``IoU`` - Use the Intersection over Union between objects as a feature for linking. This option only applies if your input is a segmentation. The provided weights will be multiplied by the IoU to get the cost for linking two objects. This weight should usually be negative, so that higher IoUs are more likely to be linked.

Run Viewer
**********
The ``Run Viewer`` contains the following information:

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
