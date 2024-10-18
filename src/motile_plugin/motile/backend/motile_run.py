from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from motile_plugin.data_model import SolutionTracks
from motile_toolbox.candidate_graph.graph_attributes import NodeAttr

from .solver_params import SolverParams

if TYPE_CHECKING:
    import networkx as nx

STAMP_FORMAT = "%m%d%Y_%H%M%S"
PARAMS_FILENAME = "solver_params.json"
IN_SEG_FILENAME = "input_segmentation.npy"
IN_POINTS_FILENAME = "input_points.npy"
GAPS_FILENAME = "gaps.txt"


class MotileRun(SolutionTracks):
    """An object representing a motile tracking run. Contains a name,
    parameters, time of creation, information about the solving process
    (status and list of solver gaps), and optionally the input and output
    segmentations and tracks. Mostly used for passing around the set of
    attributes needed to specify a run, as well as saving and loading.
    """

    def __init__(
        self,
        graph: nx.DiGraph,
        segmentation: np.ndarray | None,
        run_name: str,
        time_attr: str = NodeAttr.TIME.value,
        pos_attr: str | tuple[str] | list[str] = NodeAttr.POS.value,
        scale: list[float] | None = None,
        solver_params: SolverParams | None = None,
        input_segmentation: np.ndarray | None = None,
        input_points: np.ndarray | None = None,
        time: datetime | None = None,
        gaps: list[float] | None = None,
        status: str = "done",
    ):
        super().__init__(
            graph,
            segmentation=segmentation,
            time_attr=time_attr,
            pos_attr=pos_attr,
            scale=scale,
        )
        self.run_name = run_name
        self.solver_params = solver_params
        self.input_segmentation = input_segmentation
        self.input_points = input_points
        self.gaps = gaps
        self.status = status
        self.time = datetime.now() if time is None else time

    def _make_id(self) -> str:
        """Combine the time and run name into a unique id for the run

        Returns:
            str: A unique id combining the timestamp and run name
        """
        stamp = self.time.strftime(STAMP_FORMAT)
        return f"{stamp}_{self.run_name}"

    @staticmethod
    def _unpack_id(_id: str) -> tuple[datetime, str]:
        """Unpack a string id created with _make_id into the time and run name

        Args:
            _id (str): The id to unpack into time and run name

        Raises:
            ValueError: If the provided id is not in the expected format

        Returns:
            tuple[datetime, str]: A tuple of time and run name
        """
        stamp_len = len(datetime.now().strftime(STAMP_FORMAT))
        stamp = _id[0:stamp_len]
        run_name = _id[stamp_len + 1 :]
        try:
            time = datetime.strptime(stamp, STAMP_FORMAT)
        except ValueError as e:
            raise ValueError(
                f"Cannot unpack id {_id} into timestamp and run name."
            ) from e
        return time, run_name

    def save(self, base_path: str | Path) -> Path:
        """Save the run in the provided directory. Creates a subdirectory from
        the timestamp and run name and stores one file for each element of the
        run in that subdirectory.

        Args:
            base_path (str | Path): The directory to save the run in.

        Returns:
            (Path): The Path that the run was saved in. The last part of the
            path is the directory that was created to store the run.
        """
        base_path = Path(base_path)
        run_dir = base_path / self._make_id()
        Path.mkdir(run_dir)
        super().save(run_dir)
        self._save_params(run_dir)
        if self.input_segmentation is not None:
            self._save_array(run_dir, IN_SEG_FILENAME, self.input_segmentation)
        if self.input_points is not None:
            self._save_array(run_dir, IN_POINTS_FILENAME, self.input_points)
        self._save_list(list_to_save=self.gaps, run_dir=run_dir, filename=GAPS_FILENAME)
        return run_dir

    @classmethod
    def load(cls, run_dir: Path | str, output_required: bool = True):
        """Load a run from disk into memory.

        Args:
            run_dir (Path | str): A directory containing the saved run.
                Should be the subdirectory created by MotileRun.save that
                includes the timestamp and run name.
            output_required (bool): If the model outputs are required.
                If true, will raise an error if the output files are not found.
                Defualts to True.

        Returns:
            MotileRun: The run saved in the provided directory.
        """
        if isinstance(run_dir, str):
            run_dir = Path(run_dir)
        time, run_name = cls._unpack_id(run_dir.stem)
        params = cls._load_params(run_dir)
        input_segmentation = cls._load_array(run_dir, IN_SEG_FILENAME, required=False)
        input_points = cls._load_array(run_dir, IN_POINTS_FILENAME, required=False)
        output_seg_required = output_required and input_segmentation is not None
        tracks = SolutionTracks.load(run_dir, seg_required=output_seg_required)
        gaps = cls._load_list(run_dir=run_dir, filename=GAPS_FILENAME, required=False)
        return cls(
            graph=tracks.graph,
            segmentation=tracks.segmentation,
            run_name=run_name,
            solver_params=params,
            input_segmentation=input_segmentation,
            input_points=input_points,
            time=time,
            gaps=gaps,
            pos_attr=tracks.pos_attr,
            time_attr=tracks.time_attr,
            scale=tracks.scale,
        )

    def _save_params(self, run_dir: Path):
        """Save the run parameters in the provided run directory. Currently
        dumps the parameters dict into a json file.

        Args:
            run_dir (Path): A directory in which to save the parameters file.
        """
        params_file = run_dir / PARAMS_FILENAME
        with open(params_file, "w") as f:
            json.dump(self.solver_params.__dict__, f)

    @staticmethod
    def _load_params(run_dir: Path) -> SolverParams:
        """Load parameters from the parameters json file in the provided
        directory.

        Args:
            run_dir (Path): The directory in which to find the parameters file.

        Raises:
            FileNotFoundError: If the parameters file is not found in the
                provided directory.

        Returns:
            SolverParams: The solver parameters loaded from disk.
        """
        params_file = run_dir / PARAMS_FILENAME
        if not params_file.is_file():
            raise FileNotFoundError(f"Parameters not found at {params_file}")
        with open(params_file) as f:
            params_dict = json.load(f)
        return SolverParams(**params_dict)

    def _save_array(self, run_dir: Path, filename: str, array: np.ndarray):
        """Save a segmentation as a numpy array using np.save. In the future,
        could be changed to use zarr or other file types.

        Args:
            run_dir (Path): The directory in which to save the segmentation
            filename (str): The filename to use
            array (np.array): The array to save
        """
        out_path = run_dir / filename
        np.save(out_path, array)

    @staticmethod
    def _load_array(
        run_dir: Path, filename: str, required: bool = True
    ) -> np.ndarray | None:
        """Load an array from file using np.load. In the future,
        could be lazy loading from a zarr.

        Args:
            run_dir (Path): The base run directory containing the array
            filename (str): The name of the file to load
            required (bool, optional): If true, will fail if the array
                file is not present. If false, will return None if the file
                is not present. Defaults to True.

        Raises:
            FileNotFoundError: If the array file is not found, and
                it was required.

        Returns:
            np.ndarray | None: The array, or None if the file was
                not found and not required.
        """
        array_path = run_dir / filename
        if array_path.is_file():
            return np.load(array_path)
        elif required:
            raise FileNotFoundError(f"No segmentation at {array_path}")
        else:
            return None

    def _save_attrs(self, directory: Path):
        """Save the time_attr, pos_attr, and scale in a json file in the given directory.

        Args:
            directory (Path):  The directory in which to save the attributes
        """
        out_path = directory / self.ATTRS_FILE
        attrs_dict = {
            "time_attr": self.time_attr
            if not isinstance(self.time_attr, np.ndarray)
            else self.time_attr.tolist(),
            "pos_attr": self.pos_attr
            if not isinstance(self.pos_attr, np.ndarray)
            else self.pos_attr.tolist(),
            "scale": self.scale
            if not isinstance(self.scale, np.ndarray)
            else self.scale.tolist(),
        }
        with open(out_path, "w") as f:
            json.dump(attrs_dict, f)

    def _save_list(self, list_to_save: list | None, run_dir: Path, filename: str):
        if list_to_save is None:
            return
        list_file = run_dir / filename
        with open(list_file, "w") as f:
            f.write(",".join(map(str, list_to_save)))

    @staticmethod
    def _load_list(run_dir: Path, filename: str, required: bool = True) -> list[float]:
        list_file = run_dir / filename
        if list_file.is_file():
            with open(list_file) as f:
                file_content = f.read()
            if file_content == "":
                return None
            list_values = list(map(float, file_content.split(",")))
            return list_values
        elif required:
            raise FileNotFoundError(f"No content found at {list_file}")
        else:
            return None

    def delete(self, base_path: str | Path):
        """Delete this run from the file system. Will look inside base_path
        for the directory corresponding to this run and delete it.

        Args:
            base_path (str | Path): The parent directory where the run is saved
                (not the one created by self.save).
        """
        base_path = Path(base_path)
        run_dir = base_path / self._make_id()
        # Lets be safe and remove the expected files and then the directory
        (run_dir / PARAMS_FILENAME).unlink()
        (run_dir / IN_SEG_FILENAME).unlink()
        (run_dir / GAPS_FILENAME).unlink()
        super().delete(run_dir)
