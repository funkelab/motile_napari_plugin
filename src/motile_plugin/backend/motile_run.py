import json
from datetime import datetime
from pathlib import Path

import networkx as nx
import numpy as np
from pydantic import BaseModel

from .solver_params import SolverParams

STAMP_FORMAT = "%m%d%Y_%H%M%S"
PARAMS_FILENAME = "solver_params.json"
IN_SEG_FILEANME = "input_segmentation.npy"
OUT_SEG_FILEANME = "output_segmentation.npy"
TRACKS_FILENAME = "tracks.json"
GAPS_FILENAME = "gaps.txt"


class MotileRun(BaseModel):
    """An object representing a motile tracking run."""

    run_name: str
    solver_params: SolverParams
    input_segmentation: np.ndarray | None = None
    output_segmentation: np.ndarray | None = None
    tracks: nx.DiGraph | None = None
    time: datetime = datetime.now()
    gaps: list[float] = []
    status: str = "done"
    # pydantic does not check numpy arrays
    model_config = {"arbitrary_types_allowed": True}

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

    def save(self, base_path: str | Path):
        """Save the run in the provided directory. Creates a subdirectory from
        the timestamp and run name and stores one file for each element of the 
        run in that subdirectory.

        Args:
            base_path (str | Path): The directory to save the run in.
        """
        base_path = Path(base_path)
        run_dir = base_path / self._make_id(self.time, self.run_name)
        Path.mkdir(run_dir)
        self._save_params(run_dir)
        if self.input_segmentation is not None:
            self._save_segmentation(
                run_dir, IN_SEG_FILEANME, self.input_segmentation
            )
        if self.output_segmentation is not None:
            self._save_segmentation(
                run_dir, OUT_SEG_FILEANME, self.output_segmentation
            )
        if self.tracks is not None:
            self._save_tracks(run_dir)
        self._save_gaps(run_dir)

    @classmethod
    def load(cls, run_dir: Path | str, all_required: bool = True):
        """Load a run from disk into memory. 

        Args:
            run_dir (Path | str): A directory containing the saved run.
                Should be the subdirectory created by MotileRun.save that
                includes the timestamp and run name.
            all_required (bool): If the segmentations and tracks are required.
                If true, will raise an error if the files are not found.
                Defualts to True.

        Returns:
            MotileRun: The run saved in the provided directory.
        """
        if isinstance(run_dir, str):
            run_dir = Path(run_dir)
        time, run_name = cls._unpack_id(run_dir.stem)
        params = cls._load_params(run_dir)
        input_segmentation = cls._load_segmentation(run_dir, IN_SEG_FILEANME, required=all_required)
        output_segmentation = cls._load_segmentation(run_dir, OUT_SEG_FILEANME, required=all_required)
        tracks = cls._load_tracks(run_dir, required=all_required)
        gaps = cls._load_gaps(run_dir)
        return cls(
            run_name=run_name,
            solver_params=params,
            input_segmentation=input_segmentation,
            output_segmentation=output_segmentation,
            tracks=tracks,
            time=time,
            gaps=gaps,
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

    def _save_segmentation(self, run_dir: Path, seg_file: str, segmentation: np.array):
        """Save a segmentation as a numpy array using np.save. In the future,
        could be changed to use zarr or other file types.

        Args:
            run_dir (Path): The directory in which to save the segmentation
            seg_file (str): The filename to use
            segmentation (np.array): The segmentation to save
        """
        seg_file = run_dir / seg_file
        np.save(seg_file, segmentation)

    @staticmethod
    def _load_segmentation(
        run_dir: Path, seg_file: str, required: bool = True
    ) -> np.ndarray | None:
        """Load a segmentation from file using np.load. In the future,
        could be lazy loading from a zarr.

        Args:
            run_dir (Path): The base run directory containing the segmentation
            seg_file (str): The name of the segmentation file to load
            required (bool, optional): If true, will fail if the segmentation
                file is not present. If false, will return None if the file
                is not present. Defaults to True.

        Raises:
            FileNotFoundError: If the segmentation file is not found, and
                it was required.

        Returns:
            np.ndarray | None: The segmentation, or None if the file was
                not found and not required.
        """
        seg_file = run_dir / seg_file
        if seg_file.is_file():
            return np.load(seg_file)
        elif required:
            raise FileNotFoundError(f"No segmentation at {seg_file}")
        else:
            return None

    def _save_tracks(self, run_dir: Path):
        """Save the tracks to file. Currently uses networkx node link data
        format (and saves it as json).

        Args:
            run_dir (Path): The directory in which to save the tracks file.
        """
        tracks_file = run_dir / TRACKS_FILENAME
        with open(tracks_file, "w") as f:
            json.dump(nx.node_link_data(self.tracks), f)

    @staticmethod
    def _load_tracks(run_dir: Path, required: bool = True) -> nx.DiGraph | None:
        """Load tracks from file. Currently uses networkx node link data
        format.

        Args:
            run_dir (Path): The directory in which to find the tracks file.
            required (bool, optional): Whether to fail if the tracks file is
                not found. Defaults to True.

        Raises:
            FileNotFoundError: If the tracks file is not found in the run_dir
                and it was required.

        Returns:
            nx.DiGraph | None: The tracks, or None if they were not present
                and not required.
        """
        tracks_file: Path = run_dir / TRACKS_FILENAME
        if tracks_file.is_file():
            with open(tracks_file) as f:
                json_graph = json.load(f)
            return nx.node_link_graph(json_graph, directed=True)
        elif required:
            raise FileNotFoundError(f"No tracks at {tracks_file}")
        else:
            return None

    def _save_gaps(self, run_dir: Path):
        gaps_file = run_dir / GAPS_FILENAME
        with open(gaps_file, "w") as f:
            f.write(",".join(map(str, self.gaps)))

    @staticmethod
    def _load_gaps(run_dir, required: bool = True) -> list[float]:
        gaps_file = run_dir / GAPS_FILENAME
        if gaps_file.is_file():
            with open(gaps_file) as f:
                gaps = list(map(float, f.read().split(",")))
            return gaps
        elif required:
            raise FileNotFoundError(f"No gaps found at {gaps_file}")
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
        run_dir = base_path / self._make_id(self.time, self.run_name)
        # Lets be safe and remove the expected files and then the directory
        (run_dir / PARAMS_FILENAME).unlink()
        (run_dir / IN_SEG_FILEANME).unlink()
        (run_dir / OUT_SEG_FILEANME).unlink()
        (run_dir / TRACKS_FILENAME).unlink()
        (run_dir / GAPS_FILENAME).unlink()
        run_dir.rmdir()
