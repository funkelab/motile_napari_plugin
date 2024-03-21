from typing import Optional
from pathlib import Path
from datetime import datetime
import numpy as np
import networkx as nx
import json
from .solver_params import SolverParams

STAMP_FORMAT = "%m%d%Y_%H%M%S"
PARAMS_FILENAME = "solver_params.json"
SEG_FILEANME = "segmentation.npz"
TRACKS_FILENAME = "tracks.json"


class Run():
    def __init__(
        self,
        run_name: str,
        params: SolverParams,
        segmentation: Optional[np.ndarray] = None, 
        tracks: Optional[nx.DiGraph] = None
    ) -> None:
        self.run_name = run_name
        self.params = params
        self.segmentation = segmentation
        self.tracks = tracks

    def save(self, base_path: str | Path):
        base_path = Path(base_path)
        stamp = datetime.now().strftime(STAMP_FORMAT)
        run_dir = base_path / f"{stamp}_{self.run_name}"
        Path.mkdir(run_dir)
        self._save_params(run_dir)

    @classmethod
    def load(cls, run_dir: Path):
        run_name = run_dir.stem.split('_')[-1]
        params = cls._load_params(run_dir)
        return cls(run_name, params)

    def _save_params(self, run_dir):
        params_file = run_dir / PARAMS_FILENAME
        with open(params_file, 'w') as f:
            json.dump(self.params.__dict__, f)
    
    @staticmethod
    def _load_params(run_dir):
        params_file = run_dir / PARAMS_FILENAME
        with open(params_file, 'r') as f:
            params_dict = json.load(f)
        return SolverParams(**params_dict)
    