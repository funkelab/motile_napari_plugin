# Motile Tracker

[![tests](https://github.com/funkelab/motile_tracker/workflows/tests/badge.svg)](https://github.com/funkelab/motile_tracker/actions)
[![codecov](https://codecov.io/gh/funkelab/motile_tracker/branch/main/graph/badge.svg)](https://codecov.io/gh/funkelab/motile_tracker)
[![napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/motile_tracker)](https://napari-hub.org/plugins/motile_tracker)

The full documentation of the plugin can be found [here](https://funkelab.github.io/motile_tracker/).

A plugin for tracking with [motile](https://github.com/funkelab/motile) in napari.
Motile is a library that makes it easy to solve tracking problems using optimization
by framing the task as an Integer Linear Program (ILP).
See the motile [documentation](https://funkelab.github.io/motile)
for more details on the concepts and method.

----------------------------------

## Installation

This plugin depends on [motile](https://github.com/funkelab/motile), which in
turn depends on gurobi and ilpy. These dependencies must be installed with
conda before installing the plugin with pip.

    conda create -n motile-tracker python=3.10
    conda activate motile-tracker
    conda install -c conda-forge -c funkelab -c gurobi ilpy
    pip install motile-tracker

## Issues

If you encounter any problems, please
[file an issue](https://github.com/funkelab/motile_tracker/issues)
along with a detailed description.
