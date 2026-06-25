"""DataInterface for aligned analysis CSV data (kinematics)."""

from pathlib import Path

import numpy as np
import pandas as pd
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.utils import dict_deep_update, load_dict_from_file
from pynwb import NWBFile
from pynwb.base import TimeSeries
from pynwb.behavior import BehavioralTimeSeries


class OpenFieldTestBehaviorInterface(BaseDataInterface):
    """DataInterface for reading aligned analysis CSVs and writing computed kinematics to NWB.

    The aligned CSVs contain merged DLC pose, VAME motifs, kinematics, photometry signal,
    and metadata at 30 Hz. This interface extracts only the kinematics columns (linear/angular
    velocity, acceleration, distances) since other data streams are handled by their own
    dedicated interfaces. Linear quantities (cm/s, cm) are stored with conversion=0.01 to SI.
    """

    keywords = ("kinematics", "velocity", "acceleration", "locomotion")

    def __init__(self, file_path: str | Path, verbose: bool = True):
        """Initialize OpenFieldTestBehaviorInterface.

        Parameters
        ----------
        file_path : str or Path
            Path to the aligned analysis CSV file.
        verbose : bool, optional
            Whether to print verbose output, by default True.
        """
        super().__init__(file_path=file_path, verbose=verbose)
        self.file_path = Path(file_path)

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        behavior_metadata_yaml_path = Path(__file__).parent / "behavior_metadata.yaml"
        if behavior_metadata_yaml_path.exists():
            behavioral_metadata = load_dict_from_file(behavior_metadata_yaml_path)
            metadata = dict_deep_update(metadata, behavioral_metadata)

        return metadata

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, **kwargs) -> None:
        df = pd.read_csv(self.file_path)

        behavior_module = nwbfile.processing.get("behavior")
        if behavior_module is None:
            behavior_module = nwbfile.create_processing_module(
                name="behavior", description="Processed behavioral data."
            )

        behavioral_time_series = BehavioralTimeSeries(name="Kinematics")

        behavior_metadata = metadata["Kinematics"]
        for col_name, col_info in behavior_metadata.items():
            if col_name not in df.columns:
                continue

            data = df[col_name].values.astype(np.float64)
            # Replace NaN with 0.0 for NWB compatibility
            # data = np.nan_to_num(data, nan=0.0)

            ts = TimeSeries(
                name=col_info["name"],
                data=data,
                rate=30.0,
                unit=col_info["unit"],
                conversion=col_info["conversion"],
                description=col_info["description"],
            )
            behavioral_time_series.add_timeseries(ts)

        behavior_module.add(behavioral_time_series)
