Key bindings and Mouse Functions
================================

Napari viewer and layer key bindings and mouse functions
********************************************************

.. list-table::
   :widths: 25 25
   :header-rows: 1

   * - Mouse / Key binding
     - Action
   * - Click on a point or label
     - Select this node (center view if necessary)
   * - SHIFT + click on point or label
     - Add this node to selection
   * - Mouse drag with point layer selection tool active
     - Select multiple nodes at once
   * - Q
     - | Toggle between viewing all nodes in the
       | points/labels or only those for the currently
       | selected lineages

Tree view key and mouse functions
*********************************
.. list-table::
   :widths: 25 25
   :header-rows: 1

   * - Mouse / Key binding
     - Action
   * - Click on a node
     - Select this node (center view if necessary)
   * - SHIFT + click on a node
     - Add this node to selection
   * - Scroll
     - Zoom in or out
   * - Scroll + X / Right mouse click + drag horizontally
     - Restrict zoom to the x-axis of the tree view
   * - Scroll + Y / Right mouse click + drag vertically
     - Restrict zoom to the y-axis of the tree view
   * - Mouse drag
     - Pan
   * - SHIFT + Mouse drag
     - Rectangular selection of nodes
   * - Right mouse click
     - Reset view
   * - Q
     - | Switch between viewing all lineages (vertically)\
       | or the currently selected lineages (horizontally)
   * - W
     - | Switch between plotting the lineage tree and the
       | object size
   * - Left arrow
     - Select the node to the left
   * - Right arrow
     - Select the node to the right
   * - Up arrow
     - | Select the parent node (vertical view of all
       | lineages) or the next adjacent lineage
       | (horizontal view of selected lineage)
   * - Down arrow
     - | Select the child node (vertical view of all
       | lineages) or the previous adjacent lineage
       | (horizontal view of selected lineage)

Key bindings for editing the tracks
***********************************
.. list-table::
   :widths: 25 25
   :header-rows: 1

   * - Mouse / Key binding
     - Action
   * - D
     - Delete selected nodes
   * - B
     - Break edge between two selected nodes, if existing
   * - A
     - Create edge between two selected nodes, if valid
   * - Z
     - Undo last editing action
   * - R
     - Redo last editing action


Key bindings tutorial video
***************************
This `video`_ shows how to use the different mouse and key functions, as well as their corresponding buttons, in the napari layers and the Tree View.

.. raw:: html

  <iframe src="https://drive.google.com/file/d/1cv5FbYqc5RbkNbh0YyWAL64A3tm-ugTs/preview" width="640" height="480" allow="autoplay"></iframe>

.. _video: https://drive.google.com/file/d/1cv5FbYqc5RbkNbh0YyWAL64A3tm-ugTs/preview
